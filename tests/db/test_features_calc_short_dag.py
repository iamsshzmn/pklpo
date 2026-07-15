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
    monkeypatch.setitem(
        sys.modules, "airflow.operators.python", airflow_operators_python
    )

    common = types.ModuleType("_common")
    common.airflow_log_context = lambda context, **kwargs: nullcontext("run-id")
    monkeypatch.setitem(sys.modules, "_common", common)

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


def test_run_task_returns_loop_result(
    features_dag_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def _fake_run_features_calc_short(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"rows_saved_total": 7}

    monkeypatch.setattr(
        features_dag_module, "run_features_calc_short", _fake_run_features_calc_short
    )
    monkeypatch.setattr(
        features_dag_module, "get_dag_env", lambda: {"DATABASE_URL": "db://test"}
    )
    monkeypatch.setattr(features_dag_module, "setup_env", lambda env: None)
    monkeypatch.setenv("DATABASE_URL", "db://test")

    result = features_dag_module.features_calc_short_run_task(
        dag_run=SimpleNamespace(
            conf={
                "symbols": ["BTC-USDT-SWAP"],
                "timeframes": ["1m", "5m"],
                "max_concurrent_symbols": 4,
                "max_lag_fast": 300,
                "max_lag_slow": 1500,
                "warmup_bars": 600,
            },
            run_type="manual",
        ),
        logical_date=datetime(2026, 4, 2, 16, 15),
    )

    assert result["rows_saved_total"] == 7
    assert "duration_seconds" in result
    assert calls == [
        {
            "database_url": "db://test",
            "symbols": ["BTC-USDT-SWAP"],
            "timeframes": ["1m", "5m"],
            "max_concurrent_symbols": 4,
            "is_manual_run": True,
            "max_lag_fast": 300,
            "max_lag_slow": 1500,
            "warmup_bars": 600,
        }
    ]
