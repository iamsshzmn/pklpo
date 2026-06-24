"""Tests for pipeline_recovery_controller DAG structure and configuration."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_controller_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.dag_id = kwargs.get("dag_id", "")
            self.kwargs = kwargs

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.task_id = kwargs.get("task_id", "")
            self.kwargs = kwargs

        def __rshift__(self, other: Any) -> Any:
            return other

        def __rrshift__(self, other: Any) -> Any:
            return self

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _DummyOperator
    airflow_operators_python.BranchPythonOperator = _DummyOperator
    monkeypatch.setitem(
        sys.modules, "airflow.operators.python", airflow_operators_python
    )

    airflow_utils = types.ModuleType("airflow.utils")
    monkeypatch.setitem(sys.modules, "airflow.utils", airflow_utils)

    class _TriggerRule:
        NONE_FAILED_MIN_ONE_SUCCESS = "none_failed_min_one_success"

    airflow_utils_trigger = types.ModuleType("airflow.utils.trigger_rule")
    airflow_utils_trigger.TriggerRule = _TriggerRule
    monkeypatch.setitem(
        sys.modules, "airflow.utils.trigger_rule", airflow_utils_trigger
    )

    # Stub _common (DAG-local package, not importable from test process)
    import asyncio

    _common_mod = types.ModuleType("_common")
    _common_mod.get_dag_env = lambda: "local"  # type: ignore[attr-defined]
    _common_mod.setup_env = lambda env: None  # type: ignore[attr-defined]
    _common_mod.get_or_create_event_loop = asyncio.get_event_loop  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_common", _common_mod)

    module_path = (
        Path(__file__).parents[2] / "ops/airflow/dags/pipeline_recovery_controller.py"
    )
    module_name = "tests.db._pipeline_recovery_controller_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def controller_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_controller_dag_module(monkeypatch)


def test_controller_dag_id(controller_dag_module: types.ModuleType) -> None:
    assert controller_dag_module.dag.dag_id == "pipeline_recovery_controller"


def test_controller_dag_max_active_runs(
    controller_dag_module: types.ModuleType,
) -> None:
    assert controller_dag_module.dag.kwargs["max_active_runs"] == 1


def test_controller_dag_schedule(controller_dag_module: types.ModuleType) -> None:
    assert controller_dag_module.dag.kwargs["schedule"] == "*/30 * * * *"


def test_controller_dag_catchup_disabled(
    controller_dag_module: types.ModuleType,
) -> None:
    assert controller_dag_module.dag.kwargs["catchup"] is False


def test_controller_dag_dry_mode_is_false(
    controller_dag_module: types.ModuleType,
) -> None:
    """DRY_MODE is False — Stage 6 enables real recovery triggers."""
    assert controller_dag_module.DRY_MODE is False


def test_controller_dag_task_ids_present(
    controller_dag_module: types.ModuleType,
) -> None:
    expected_tasks = {
        "collect_recovery_state",
        "choose_recovery_action",
        "branch_recovery_action",
        "trigger_repair",
        "trigger_bootstrap",
        "skip_recovery",
        "record_controller_completion",
    }
    actual_tasks = {
        controller_dag_module.collect_recovery_state.task_id,
        controller_dag_module.choose_recovery_action.task_id,
        controller_dag_module.branch_recovery_action.task_id,
        controller_dag_module.trigger_repair.task_id,
        controller_dag_module.trigger_bootstrap.task_id,
        controller_dag_module.skip_recovery.task_id,
        controller_dag_module.record_controller_completion.task_id,
    }
    assert actual_tasks == expected_tasks


def test_controller_dag_target_dag_ids(controller_dag_module: types.ModuleType) -> None:
    assert controller_dag_module.REPAIR_DAG_ID == "okx_swap_repair_v1"
    assert controller_dag_module.BOOTSTRAP_DAG_ID == "okx_swap_ohlcv_bootstrap_v1"


def test_record_completion_has_permissive_trigger_rule(
    controller_dag_module: types.ModuleType,
) -> None:
    tr = controller_dag_module.record_controller_completion.kwargs.get("trigger_rule")
    assert tr == "none_failed_min_one_success"


def test_branch_always_returns_skip_in_dry_mode(
    controller_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In DRY_MODE, branch_recovery_action must always return skip_recovery."""
    monkeypatch.setattr(controller_dag_module, "DRY_MODE", True)

    class _TI:
        def xcom_pull(self, task_ids: str, key: str) -> Any:
            return {"branch": "trigger_repair"}

    result = controller_dag_module.task_branch_recovery_action(
        ti=_TI(), dag_run=SimpleNamespace(run_id="test"), logical_date=None
    )
    assert result == "skip_recovery"


def test_branch_returns_correct_branch_when_not_dry_mode(
    controller_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When DRY_MODE=False, branch follows chosen action."""
    monkeypatch.setattr(controller_dag_module, "DRY_MODE", False)

    class _TI:
        def __init__(self, branch: str) -> None:
            self._branch = branch

        def xcom_pull(self, task_ids: str, key: str) -> Any:
            return {"branch": self._branch}

    result_repair = controller_dag_module.task_branch_recovery_action(
        ti=_TI("trigger_repair"),
        dag_run=SimpleNamespace(run_id="test"),
        logical_date=None,
    )
    assert result_repair == "trigger_repair"

    result_bootstrap = controller_dag_module.task_branch_recovery_action(
        ti=_TI("trigger_bootstrap"),
        dag_run=SimpleNamespace(run_id="test"),
        logical_date=None,
    )
    assert result_bootstrap == "trigger_bootstrap"

    result_skip = controller_dag_module.task_branch_recovery_action(
        ti=_TI("skip_recovery"),
        dag_run=SimpleNamespace(run_id="test"),
        logical_date=None,
    )
    assert result_skip == "skip_recovery"


def test_choose_recovery_action_returns_skip_when_no_triggered(
    controller_dag_module: types.ModuleType,
) -> None:
    """choose_recovery_action must return skip when collect_recovery_state has no triggered actions."""

    class _TI:
        def xcom_pull(self, task_ids: str, key: str) -> Any:
            return {"triggered_actions": [], "decision_count": 1}

    result = controller_dag_module.task_choose_recovery_action(
        ti=_TI(), dag_run=SimpleNamespace(run_id="test"), logical_date=None
    )
    assert result["branch"] == "skip_recovery"
    assert result["target_dag_id"] is None


def test_choose_recovery_action_picks_first_triggered_action(
    controller_dag_module: types.ModuleType,
) -> None:
    """choose_recovery_action selects the first triggered action (highest priority)."""

    class _TI:
        def xcom_pull(self, task_ids: str, key: str) -> Any:
            return {
                "triggered_actions": [
                    {
                        "action_kind": "bootstrap",
                        "reason": "bootstrap_state_missing",
                        "symbol": "BTC-USDT-SWAP",
                        "timeframe": "1H",
                        "target_dag_id": "okx_swap_ohlcv_bootstrap_v1",
                        "trigger_conf": {"symbols": ["BTC-USDT-SWAP"]},
                    }
                ]
            }

    result = controller_dag_module.task_choose_recovery_action(
        ti=_TI(), dag_run=SimpleNamespace(run_id="test"), logical_date=None
    )
    assert result["branch"] == "trigger_bootstrap"
    assert result["target_dag_id"] == "okx_swap_ohlcv_bootstrap_v1"
    assert result["action_kind"] == "bootstrap"
