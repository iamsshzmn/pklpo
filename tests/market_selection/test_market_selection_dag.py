from __future__ import annotations

import importlib.util
import sys
import types
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_market_selection_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def __enter__(self) -> _DummyDAG:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def __rshift__(self, other: Any) -> Any:
            return other

        def __rrshift__(self, other: Any) -> _DummyOperator:
            return self

    common_module = types.ModuleType("_common")
    common_module.airflow_log_context = lambda *args, **kwargs: nullcontext()
    common_module.get_dag_env = lambda: {}
    common_module.get_or_create_event_loop = lambda: None
    common_module.setup_env = lambda env: None
    monkeypatch.setitem(sys.modules, "_common", common_module)

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

    airflow_operators_trigger = types.ModuleType("airflow.operators.trigger_dagrun")
    airflow_operators_trigger.TriggerDagRunOperator = _DummyOperator
    monkeypatch.setitem(
        sys.modules, "airflow.operators.trigger_dagrun", airflow_operators_trigger
    )

    airflow_operators_empty = types.ModuleType("airflow.operators.empty")
    airflow_operators_empty.EmptyOperator = _DummyOperator
    monkeypatch.setitem(sys.modules, "airflow.operators.empty", airflow_operators_empty)

    airflow_sensors = types.ModuleType("airflow.sensors")
    monkeypatch.setitem(sys.modules, "airflow.sensors", airflow_sensors)

    airflow_sensors_external = types.ModuleType("airflow.sensors.external_task")
    airflow_sensors_external.ExternalTaskSensor = _DummyOperator
    monkeypatch.setitem(
        sys.modules, "airflow.sensors.external_task", airflow_sensors_external
    )

    module_path = Path("D:/projects/pklpo/ops/airflow/dags/market_selection.py")
    module_name = "tests.market_selection._market_selection_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def market_selection_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_market_selection_module(monkeypatch)


def test_branch_cleanup_daily_selects_cleanup_and_logs(
    market_selection_dag_module: types.ModuleType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    context = {
        "logical_date": datetime(2026, 1, 1, 0, 0),
        "dag_run": SimpleNamespace(run_id="scheduled__2026-01-01T00:00:00+00:00"),
        "ti": SimpleNamespace(try_number=1),
    }

    branch = market_selection_dag_module.branch_cleanup_daily(**context)

    assert branch == "cleanup_old_market_selection_data"
    assert "branch_cleanup_daily decision" in caplog.text
    assert "selected_branch=cleanup_old_market_selection_data" in caplog.text


def test_branch_skip_or_trigger_selects_trigger_and_logs(
    market_selection_dag_module: types.ModuleType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Ti:
        try_number = 2

        @staticmethod
        def xcom_pull(task_ids: str) -> dict[str, Any]:
            assert task_ids == "prepare_features_calc_trigger"
            return {"skip_trigger": False, "symbols": ["BTC-USDT", "ETH-USDT"]}

    caplog.set_level("INFO")
    context = {
        "logical_date": datetime(2026, 1, 1, 4, 0),
        "dag_run": SimpleNamespace(run_id="scheduled__2026-01-01T04:00:00+00:00"),
        "ti": _Ti(),
    }

    branch = market_selection_dag_module.branch_skip_or_trigger(**context)

    assert branch == "trigger_features_calc"
    assert "branch_skip_or_trigger decision" in caplog.text
    assert "selected_branch=trigger_features_calc" in caplog.text


def test_run_pipeline_task_handles_non_numeric_execution_time(
    market_selection_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            coro.close()
            return {
                "success": True,
                "ts_version": 1,
                "ts_eval": 1234567890,
                "universe_size": 10,
                "status": "published",
                "global_regime": "RANGE",
                "eligible_counts": {"h1": 10},
                "execution_time_seconds": "not-a-number",
                "config_hash": "abc",
                "error_message": None,
            }

    monkeypatch.setattr(
        market_selection_dag_module,
        "get_dag_env",
        lambda: {"DATABASE_URL": "db://test"},
    )
    monkeypatch.setattr(market_selection_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        market_selection_dag_module, "get_or_create_event_loop", lambda: _Loop()
    )

    caplog.set_level("INFO")
    context = {
        "params": {"top_n": 30},
        "dag_run": SimpleNamespace(conf={}, run_id="manual__2026-01-01T04:00:00+00:00"),
        "logical_date": datetime(2026, 1, 1, 4, 0),
        "ti": SimpleNamespace(try_number=1),
    }
    result = market_selection_dag_module.run_pipeline_task(**context)

    assert result["success"] is True
    assert "run_pipeline finish" in caplog.text
    assert "time=n/a" in caplog.text


def test_run_migrations_task_logs_exception_and_reraises(
    market_selection_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> bool:
            coro.close()
            raise RuntimeError("migration failed")

    monkeypatch.setattr(
        market_selection_dag_module,
        "get_dag_env",
        lambda: {"DATABASE_URL": "db://test"},
    )
    monkeypatch.setattr(market_selection_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        market_selection_dag_module, "get_or_create_event_loop", lambda: _Loop()
    )

    caplog.set_level("INFO")
    context = {
        "dag_run": SimpleNamespace(conf={}, run_id="manual__2026-01-01T00:00:00+00:00"),
        "logical_date": datetime(2026, 1, 1, 0, 0),
        "ti": SimpleNamespace(try_number=3),
    }

    with pytest.raises(RuntimeError, match="migration failed"):
        market_selection_dag_module.run_migrations_task(**context)

    assert "run_migrations failed" in caplog.text
