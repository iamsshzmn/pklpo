"""Smoke tests for okx_swap_ohlcv_bootstrap_v1 DAG."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_bootstrap_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            self.tasks: list[Any] = []
            self.schedule_interval = kwargs.get("schedule_interval")

        def __enter__(self) -> _DummyDAG:
            return self

        def __exit__(self, *exc: Any) -> None:
            pass

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.task_id: str = kwargs.get("task_id", "")
            self.args = args
            self.kwargs = kwargs

        def __rshift__(self, other: Any) -> Any:
            return other

    # Patch DAG to track tasks automatically
    _dag_instance: list[_DummyDAG] = []

    class _TrackingDAG(_DummyDAG):
        def __enter__(self) -> _TrackingDAG:
            _dag_instance.clear()
            _dag_instance.append(self)
            return self

    class _TrackingOperator(_DummyOperator):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            if _dag_instance:
                _dag_instance[0].tasks.append(self)

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _TrackingDAG  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    class _AirflowFailException(Exception):
        pass

    airflow_exceptions = types.ModuleType("airflow.exceptions")
    airflow_exceptions.AirflowFailException = _AirflowFailException  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow.exceptions", airflow_exceptions)

    airflow_models = types.ModuleType("airflow.models")
    monkeypatch.setitem(sys.modules, "airflow.models", airflow_models)

    airflow_models_param = types.ModuleType("airflow.models.param")

    class _DummyParam:
        def __init__(self, default: Any, **kwargs: Any) -> None:
            self.default = default
            self.kwargs = kwargs

    airflow_models_param.Param = _DummyParam  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow.models.param", airflow_models_param)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _TrackingOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "airflow.operators.python", airflow_operators_python
    )

    candles_bootstrap = types.ModuleType("src.candles.bootstrap")
    candles_bootstrap.create_candles_airflow_callbacks = lambda: SimpleNamespace(  # type: ignore[attr-defined]
        on_failure_callback="failure_cb",
        on_success_callback="success_cb",
        on_retry_callback="retry_cb",
    )
    monkeypatch.setitem(sys.modules, "src.candles.bootstrap", candles_bootstrap)

    module_path = Path("D:/projects/pklpo/ops/airflow/dags/okx_swap_ohlcv_bootstrap_v1.py")
    module_name = "tests.db._okx_swap_ohlcv_bootstrap_v1_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def bootstrap_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_bootstrap_dag_module(monkeypatch)


@pytest.mark.smoke
def test_bootstrap_dag_loads_without_error(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """DAG file must be importable and expose the expected task IDs."""
    dag = getattr(bootstrap_dag_module, "dag", None)
    assert dag is not None, "module must expose a 'dag' variable"

    task_ids = {t.task_id for t in dag.tasks}
    expected = {
        "validate_conf",
        "preflight_instrument_check",
        "init_bootstrap_state",
        "coverage_report",
        "bootstrap_symbol_tf",
        "validate_bootstrap_xcom",
        "enqueue_indicator_recalc",
        "publish_bootstrap_report",
        "publish_bootstrap_ops",
    }
    assert expected.issubset(task_ids), f"missing tasks: {expected - task_ids}"


@pytest.mark.smoke
def test_bootstrap_dag_schedule_is_none(
    bootstrap_dag_module: types.ModuleType,
) -> None:
    """Bootstrap DAG must have schedule=None (manual trigger only)."""
    dag = getattr(bootstrap_dag_module, "dag", None)
    assert dag is not None
    assert dag.schedule_interval is None, "bootstrap must be manual-trigger only"
