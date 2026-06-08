from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _load_features_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
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
    monkeypatch.setitem(sys.modules, "airflow.operators.python", airflow_operators_python)

    features_api = types.ModuleType("src.features.api")
    features_api.run_features_calc_short = object()
    features_api.run_features_calc_short_validate = object()
    monkeypatch.setitem(sys.modules, "src.features.api", features_api)

    features_bootstrap = types.ModuleType("src.features.bootstrap")
    features_bootstrap.create_feature_airflow_callbacks = lambda: SimpleNamespace(
        on_failure_callback=None,
        on_success_callback=None,
        sla_miss_callback=None,
    )
    monkeypatch.setitem(sys.modules, "src.features.bootstrap", features_bootstrap)

    module_path = Path("D:/projects/pklpo/ops/airflow/dags/features_calc_short.py")
    module_name = "tests.db._features_calc_short_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def features_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_features_dag_module(monkeypatch)


def test_prepare_storage_task_returns_loop_result(
    features_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_indicators_partition_maintenance(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"created_count": 2, "existing_count": 5}

    db_interfaces = types.ModuleType("src.db.indicators_partition.interfaces")
    db_interfaces.run_indicators_partition_maintenance = _fake_run_indicators_partition_maintenance
    monkeypatch.setitem(sys.modules, "src.db.indicators_partition.interfaces", db_interfaces)

    monkeypatch.setattr(
        features_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(features_dag_module, "setup_env", lambda env: None)

    result = features_dag_module.features_calc_short_prepare_storage_task(
        dag_run=SimpleNamespace(
            conf={
                "partition_months_back": 2,
                "partition_months_ahead": 4,
            }
        ),
        logical_date=datetime(2026, 4, 2, 16, 15),
    )

    assert result == {"created_count": 2, "existing_count": 5}
    assert calls == [
        {
            "months_back": 2,
            "months_ahead": 4,
            "reference_dt": datetime(2026, 4, 2, 16, 15),
            "require_parent_pk": True,
            "repair_parent_schema": True,
        }
    ]
