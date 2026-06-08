from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

import pytest


def _load_okx_swap_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
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

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _DummyOperator
    monkeypatch.setitem(sys.modules, "airflow.operators.python", airflow_operators_python)

    module_path = Path("D:/projects/pklpo/ops/airflow/dags/okx_swap_ohlcv_sync_v2.py")
    module_name = "tests.db._okx_swap_ohlcv_sync_v2_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def okx_swap_dag_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    return _load_okx_swap_dag_module(monkeypatch)


class _TaskInstance:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def xcom_pull(self, task_ids: str, key: str) -> dict[str, Any]:
        assert task_ids == "swap_sync"
        assert key == "return_value"
        return self._payload


def test_validate_swap_sync_xcom_accepts_skipped_payload(
    okx_swap_dag_module: types.ModuleType,
) -> None:
    payload = {"mode": "fast", "skipped": True, "reason": "data_fresh"}

    result = okx_swap_dag_module.validate_swap_sync_xcom_task(ti=_TaskInstance(payload))

    assert result == payload


def test_validate_swap_sync_xcom_accepts_success_payload(
    okx_swap_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "fast",
        "skipped": False,
        "timeframes": ["1m", "5m"],
        "symbols_count": 2,
        "total_symbols_processed": 2,
        "duration_sec": 3.5,
        "rows_upserted_total": 42,
        "errors_count": 1,
        "candles_per_second": 12.0,
        "api_429_count": 1,
        "api_timeout_count": 0,
        "today_fill": {"rows_today": 42},
    }

    result = okx_swap_dag_module.validate_swap_sync_xcom_task(ti=_TaskInstance(payload))

    assert result == payload


def test_validate_swap_sync_xcom_fails_on_zero_rows_upserted(
    okx_swap_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "fast",
        "skipped": False,
        "timeframes": ["1m"],
        "symbols_count": 1,
        "total_symbols_processed": 1,
        "duration_sec": 1.0,
        "rows_upserted_total": 0,
        "errors_count": 1,
        "candles_per_second": 0.0,
        "api_429_count": 0,
        "api_timeout_count": 0,
        "today_fill": {},
    }

    with pytest.raises(ValueError, match="rows_upserted_total == 0"):
        okx_swap_dag_module.validate_swap_sync_xcom_task(ti=_TaskInstance(payload))


def test_validate_swap_sync_xcom_fails_on_zero_symbols_processed(
    okx_swap_dag_module: types.ModuleType,
) -> None:
    payload = {
        "mode": "fast",
        "skipped": False,
        "timeframes": ["1m"],
        "symbols_count": 1,
        "total_symbols_processed": 0,
        "duration_sec": 1.0,
        "rows_upserted_total": 5,
        "errors_count": 1,
        "candles_per_second": 0.0,
        "api_429_count": 0,
        "api_timeout_count": 0,
        "today_fill": {},
    }

    with pytest.raises(ValueError, match="total_symbols_processed == 0"):
        okx_swap_dag_module.validate_swap_sync_xcom_task(ti=_TaskInstance(payload))
