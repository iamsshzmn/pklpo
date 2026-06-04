"""Smoke tests for swap_ohlcv_retention DAG."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_retention_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            self.tasks: list[Any] = []
            self.schedule = kwargs.get("schedule")

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.task_id: str = kwargs.get("task_id", "")
            self.args = args
            self.kwargs = kwargs

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    class _AirflowSkipException(Exception):
        pass

    airflow_exceptions = types.ModuleType("airflow.exceptions")
    airflow_exceptions.AirflowSkipException = _AirflowSkipException  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow.exceptions", airflow_exceptions)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")

    def _tracking_operator(*args: Any, **kwargs: Any) -> _DummyOperator:
        operator = _DummyOperator(*args, **kwargs)
        dag = kwargs.get("dag")
        if dag is not None:
            dag.tasks.append(operator)
        return operator

    airflow_operators_python.PythonOperator = _tracking_operator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "airflow.operators.python", airflow_operators_python
    )

    common_module = types.ModuleType("_common")
    common_module.get_dag_env = lambda job_name_default: {}  # type: ignore[attr-defined]
    common_module.setup_env = lambda env: None  # type: ignore[attr-defined]

    class _Loop:
        def run_until_complete(self, value: Any) -> Any:
            if hasattr(value, "send"):
                try:
                    value.send(None)
                except StopIteration as exc:
                    return exc.value
            return value

    common_module.get_or_create_event_loop = lambda: _Loop()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "_common", common_module)

    candles_bootstrap = types.ModuleType("src.candles.bootstrap")
    candles_bootstrap.create_candles_airflow_callbacks = lambda: SimpleNamespace(  # type: ignore[attr-defined]
        on_failure_callback="failure_cb",
        on_success_callback="success_cb",
        on_retry_callback="retry_cb",
    )
    monkeypatch.setitem(sys.modules, "src.candles.bootstrap", candles_bootstrap)

    module_path = Path("D:/projects/pklpo/ops/airflow/dags/swap_ohlcv_retention.py")
    module_name = "tests.db._swap_ohlcv_retention_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def retention_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_retention_dag_module(monkeypatch)


def test_retention_dag_runs_daily_at_quiet_slot(
    retention_dag_module: types.ModuleType,
) -> None:
    dag = retention_dag_module.dag
    assert dag.schedule == "0 4 * * *"


def test_cleanup_task_uses_ohlcv_write_pool(
    retention_dag_module: types.ModuleType,
) -> None:
    cleanup_task = next(t for t in retention_dag_module.dag.tasks if t.task_id == "cleanup_swap_ohlcv")
    assert cleanup_task.kwargs["pool"] == "ohlcv_write_pool"
    assert cleanup_task.kwargs["pool_slots"] == 1


def test_cleanup_task_skips_when_bootstrap_is_active(
    retention_dag_module: types.ModuleType,
) -> None:
    AirflowSkipException = sys.modules["airflow.exceptions"].AirflowSkipException

    async def _unsafe() -> bool:
        return False

    async def _fail_cleanup(*_: Any, **__: Any) -> list[dict[str, Any]]:
        raise AssertionError("cleanup should not run while bootstrap is active")

    retention_dag_module._bootstrap_cleanup_is_safe = _unsafe
    retention_dag_module._run_cleanup = _fail_cleanup
    retention_dag_module.get_dag_env = lambda: {}
    retention_dag_module.setup_env = lambda env: None

    with pytest.raises(AirflowSkipException, match="bootstrap in progress"):
        retention_dag_module.cleanup_swap_ohlcv_task(
            dag_run=SimpleNamespace(run_id="manual__test")
        )
