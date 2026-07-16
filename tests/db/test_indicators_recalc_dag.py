from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest


def _load_dag(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    class _DummyDAG:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    class _DummyOperator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    airflow_module = types.ModuleType("airflow")
    airflow_module.DAG = _DummyDAG  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "airflow", airflow_module)

    airflow_operators = types.ModuleType("airflow.operators")
    monkeypatch.setitem(sys.modules, "airflow.operators", airflow_operators)

    airflow_operators_python = types.ModuleType("airflow.operators.python")
    airflow_operators_python.PythonOperator = _DummyOperator  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "airflow.operators.python",
        airflow_operators_python,
    )

    module_path = Path(__file__).parents[2] / "ops/airflow/dags/indicators_recalc.py"
    module_name = "tests.db._indicators_recalc_dag"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_indicators_recalc_dag_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_dag(monkeypatch)
    source = (
        Path(__file__).parents[2] / "ops/airflow/dags/indicators_recalc.py"
    ).read_text(encoding="utf-8")

    assert module.dag.kwargs["dag_id"] == "indicators_recalc"
    assert module.dag.kwargs["schedule"] == "*/10 * * * *"
    assert module.dag.kwargs["max_active_runs"] == 1
    assert "|| ' minutes'" not in source
    assert "CAST(:stale_after_minutes AS integer) * interval '1 minute'" in source
    assert module.drain_indicator_recalc_queue.kwargs["task_id"] == (
        "drain_indicator_recalc_queue"
    )
    assert module.drain_indicator_recalc_queue.kwargs["pool"] == "compute_pool"


def test_drain_indicator_recalc_queue_marks_completed_and_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_dag(monkeypatch)
    rows = [
        {
            "id": 1,
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "range_start_ts": 100,
            "range_end_ts": 200,
            "warmup_bars": 500,
            "detail": {"specs": ["rsi"]},
        },
        {
            "id": 2,
            "symbol": "ETH-USDT-SWAP",
            "timeframe": "1H",
            "range_start_ts": 100,
            "range_end_ts": 200,
            "warmup_bars": 500,
            "detail": {"specs": ["rsi"]},
        },
    ]
    marked: list[tuple[int, str, dict[str, Any]]] = []

    async def _claim_rows(
        *, limit: int, stale_after_minutes: int
    ) -> list[dict[str, Any]]:
        assert limit == 25
        assert stale_after_minutes == 60
        return rows

    async def _process_row(row: dict[str, Any], *, run_id: str) -> dict[str, Any]:
        if row["id"] == 1:
            return {"status": "completed", "rows_written": 7, "run_id": run_id}
        return {
            "status": "blocked",
            "rows_written": 0,
            "blocked_reason": "insufficient_history",
            "run_id": run_id,
        }

    async def _mark_row(row_id: int, *, status: str, detail: dict[str, Any]) -> None:
        marked.append((row_id, status, detail))

    monkeypatch.setattr(module, "_claim_indicator_recalc_rows", _claim_rows)
    monkeypatch.setattr(module, "_process_indicator_recalc_row", _process_row)
    monkeypatch.setattr(module, "_mark_indicator_recalc_row", _mark_row)

    result = module.drain_indicator_recalc_queue_task(
        dag_run=types.SimpleNamespace(run_id="manual__2026-05-25")
    )

    assert result == {
        "claimed": 2,
        "completed": 1,
        "blocked": 1,
        "failed": 0,
    }
    assert marked == [
        (
            1,
            "completed",
            {"status": "completed", "rows_written": 7, "run_id": "manual__2026-05-25"},
        ),
        (
            2,
            "blocked",
            {
                "status": "blocked",
                "rows_written": 0,
                "blocked_reason": "insufficient_history",
                "run_id": "manual__2026-05-25",
            },
        ),
    ]
