from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_partition_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def __rshift__(self, other: Any) -> Any:
            return other

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _DummyOperator
    monkeypatch.setitem(
        sys.modules, "airflow.operators.python", airflow_operators_python
    )

    module_path = Path(
        str(
            Path(__file__).parents[2]
            / "ops/airflow/dags/indicators_partition_maintenance.py"
        )
    )
    module_name = "tests.db._indicators_partition_maintenance_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def partition_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_partition_dag_module(monkeypatch)


def test_run_partition_maintenance_task_returns_loop_result(
    partition_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            coro.close()
            return {"created_count": 1, "existing_count": 4}

    monkeypatch.setattr(
        partition_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(partition_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        partition_dag_module, "get_or_create_event_loop", lambda: _Loop()
    )

    result = partition_dag_module.run_partition_maintenance_task(
        dag_run=SimpleNamespace(
            conf={
                "months_back": 2,
                "months_ahead": 4,
                "reference_dt": "2026-03-07T00:00:00Z",
                "require_parent_pk": True,
            }
        ),
        logical_date=datetime(2026, 3, 7, 1, 0),
    )

    assert result["created_count"] == 1
    assert result["existing_count"] == 4


def test_validate_partition_horizon_task_reraises_failures(
    partition_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Loop:
        @staticmethod
        def run_until_complete(coro: Any) -> dict[str, Any]:
            coro.close()
            raise RuntimeError("missing partitions")

    monkeypatch.setattr(
        partition_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(partition_dag_module, "setup_env", lambda env: None)
    monkeypatch.setattr(
        partition_dag_module, "get_or_create_event_loop", lambda: _Loop()
    )

    with pytest.raises(RuntimeError, match="missing partitions"):
        partition_dag_module.validate_partition_horizon_task(
            dag_run=SimpleNamespace(conf={}),
            logical_date=datetime(2026, 3, 7, 1, 0),
        )
