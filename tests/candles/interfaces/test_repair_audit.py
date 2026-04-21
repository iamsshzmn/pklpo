from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from src.candles.interfaces import repair_audit


@pytest.mark.asyncio
async def test_write_swap_repair_audit_builds_records_per_timeframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[dict[str, Any]]] = []

    class _FakeRepository:
        async def insert_records(self, records: list[dict[str, Any]]) -> int:
            calls.append(records)
            return len(records)

    monkeypatch.setattr(repair_audit, "SwapRepairAuditRepository", _FakeRepository)

    written = await repair_audit.write_swap_repair_audit(
        validated_conf={
            "trigger": "repair-all-swaps",
            "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            "mode": "apply",
            "repair_strategy": "gap-repair",
            "auto_apply_window": True,
        },
        preview_payloads=[
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "gap_tasks": 2,
                "requested_bars": 20,
                "expected_iteration_count": 2,
            },
            {
                "symbol": "ETH-USDT-SWAP",
                "timeframe": "1m",
                "gap_tasks": 1,
                "requested_bars": 10,
                "expected_iteration_count": 1,
            }
        ],
        summary_payloads=[
            {
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "mode": "apply",
                "strategy": "gap-repair",
                "window": {"start_ts_ms": 10, "end_ts_ms": 100},
                "gap_tasks": 2,
                "requested_bars": 20,
                "remaining_gap_tasks": 0,
                "remaining_requested_bars": 0,
                "verification_method": "gap-detection",
                "rows_written": 20,
                "fetch_calls": 2,
                "verified": True,
                "outcome": "success",
                "received_bars": 20,
                "remaining_missing_before": 20,
                "remaining_missing_after": 0,
                "progress": 20,
                "api_fill_ratio": 1.0,
                "write_success_ratio": 1.0,
            },
            {
                "symbol": "ETH-USDT-SWAP",
                "timeframe": "1m",
                "mode": "apply",
                "strategy": "gap-repair",
                "window": {"start_ts_ms": 100, "end_ts_ms": 200},
                "gap_tasks": 1,
                "requested_bars": 10,
                "remaining_gap_tasks": 0,
                "remaining_requested_bars": 0,
                "verification_method": "gap-detection",
                "rows_written": 10,
                "fetch_calls": 1,
                "verified": True,
            }
        ],
        dag_id="okx_swap_repair_v1",
        dag_run_id="manual__2026-04-16T10:00:00+00:00",
        logical_date=datetime(2026, 4, 16, 10, 0, tzinfo=UTC),
    )

    assert written == 2
    assert calls
    assert calls[0][0]["dag_id"] == "okx_swap_repair_v1"
    assert calls[0][0]["preview_payload"]["expected_iteration_count"] == 2
    assert calls[0][0]["summary_payload"]["rows_written"] == 20
    assert calls[0][1]["symbol"] == "ETH-USDT-SWAP"
    assert calls[0][1]["preview_payload"]["expected_iteration_count"] == 1
    assert calls[0][1]["summary_payload"]["rows_written"] == 10

    btc_record = calls[0][0]
    assert btc_record["outcome"] == "success"
    assert btc_record["received_bars"] == 20
    assert btc_record["remaining_missing_before"] == 20
    assert btc_record["remaining_missing_after"] == 0
    assert btc_record["progress"] == 20
    assert btc_record["api_fill_ratio"] == 1.0
    assert btc_record["write_success_ratio"] == 1.0

    eth_record = calls[0][1]
    assert eth_record["outcome"] is None
    assert eth_record["received_bars"] is None
    assert eth_record["api_fill_ratio"] is None
