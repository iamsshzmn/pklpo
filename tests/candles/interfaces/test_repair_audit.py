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
            },
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
            },
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
    assert btc_record["summary_payload"]["blocked"] is False
    assert btc_record["summary_payload"]["blocked_reason"] is None
    assert btc_record["summary_payload"]["blocked_cause"] is None

    eth_record = calls[0][1]
    assert eth_record["outcome"] == "success"
    assert eth_record["received_bars"] == 0
    assert eth_record["api_fill_ratio"] == 0.0
    assert eth_record["summary_payload"]["blocked"] is False
    assert eth_record["summary_payload"]["blocked_reason"] is None
    assert eth_record["summary_payload"]["blocked_cause"] is None


@pytest.mark.asyncio
async def test_audit_payload_carries_new_outcome_fields_per_outcome_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit records must carry outcome and blocked metadata unchanged per summary.

    Asserts the mapping from ``summary_payload`` → audit record for the three
    non-failure outcome types defined in ``RepairOutcome`` (success, partial,
    empty). See REPAIR-903.
    """
    captured: list[list[dict[str, Any]]] = []

    class _FakeRepository:
        async def insert_records(self, records: list[dict[str, Any]]) -> int:
            captured.append(records)
            return len(records)

    monkeypatch.setattr(repair_audit, "SwapRepairAuditRepository", _FakeRepository)

    new_field_names = (
        "outcome",
        "received_bars",
        "remaining_missing_before",
        "remaining_missing_after",
        "progress",
        "api_fill_ratio",
        "write_success_ratio",
    )
    blocked_field_names = ("blocked", "blocked_reason", "blocked_cause")

    summaries = [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "mode": "apply",
            "strategy": "gap-repair",
            "window": {"start_ts_ms": 0, "end_ts_ms": 300_000},
            "rows_written": 5,
            "fetch_calls": 1,
            "verified": True,
            "outcome": "success",
            "received_bars": 5,
            "remaining_missing_before": 5,
            "remaining_missing_after": 0,
            "progress": 5,
            "api_fill_ratio": 1.0,
            "write_success_ratio": 1.0,
            "blocked": False,
            "blocked_reason": None,
            "blocked_cause": None,
        },
        {
            "symbol": "ETH-USDT-SWAP",
            "timeframe": "1m",
            "mode": "apply",
            "strategy": "gap-repair",
            "window": {"start_ts_ms": 0, "end_ts_ms": 300_000},
            "rows_written": 2,
            "fetch_calls": 1,
            "verified": False,
            "outcome": "partial",
            "received_bars": 2,
            "remaining_missing_before": 5,
            "remaining_missing_after": 3,
            "progress": 2,
            "api_fill_ratio": 0.4,
            "write_success_ratio": 1.0,
            "blocked": False,
            "blocked_reason": None,
            "blocked_cause": None,
        },
        {
            "symbol": "SOL-USDT-SWAP",
            "timeframe": "1m",
            "mode": "apply",
            "strategy": "gap-repair",
            "window": {"start_ts_ms": 0, "end_ts_ms": 300_000},
            "rows_written": 0,
            "fetch_calls": 1,
            "verified": False,
            "outcome": "empty",
            "received_bars": 0,
            "remaining_missing_before": 5,
            "remaining_missing_after": 5,
            "progress": 0,
            "api_fill_ratio": 0.0,
            "write_success_ratio": 0.0,
            "blocked": True,
            "blocked_reason": "empty-chunk",
            "blocked_cause": "api_returned_empty",
        },
    ]

    await repair_audit.write_swap_repair_audit(
        validated_conf={
            "trigger": "repair-all-swaps",
            "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"],
            "mode": "apply",
            "repair_strategy": "gap-repair",
            "auto_apply_window": True,
        },
        preview_payloads=None,
        summary_payloads=summaries,
        dag_id="okx_swap_repair_v1",
        dag_run_id="manual__2026-04-22T00:00:00+00:00",
        logical_date=datetime(2026, 4, 22, 0, 0, tzinfo=UTC),
    )

    assert len(captured) == 1
    records = captured[0]
    assert len(records) == 3

    for record, summary in zip(records, summaries, strict=True):
        for field_name in new_field_names:
            assert field_name in record, f"audit record missing field {field_name!r}"
            assert record[field_name] == summary[field_name], (
                f"audit {field_name!r} mismatch for {summary['symbol']}: "
                f"expected {summary[field_name]!r}, got {record[field_name]!r}"
            )
        for field_name in blocked_field_names:
            assert record["summary_payload"][field_name] == summary[field_name]

    assert [r["outcome"] for r in records] == ["success", "partial", "empty"]


@pytest.mark.asyncio
async def test_write_guard_repair_audit_writes_one_record_per_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard_payloads = [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "status": "ok",
            "strategy": "last_n_closed_bars",
            "mode": "apply",
            "repaired_count": 3,
            "corrupted_count": 1,
            "unresolved_timestamps": [],
            "affected_recalc_range": (1_700_000_000_000, 1_700_010_000_000),
            "run_id": "run-abc",
            "algo_version": "1",
            "params_hash": "abc123",
        },
        {
            "symbol": "ETH-USDT-SWAP",
            "timeframe": "4H",
            "status": "partial",
            "strategy": "last_n_closed_bars",
            "mode": "apply",
            "repaired_count": 0,
            "corrupted_count": 0,
            "unresolved_timestamps": [1_700_000_000_000, 1_700_014_400_000],
            "affected_recalc_range": None,
            "run_id": "run-abc",
            "algo_version": "1",
            "params_hash": "abc123",
        },
    ]
    validated_conf = {
        "trigger": "last-200-guard",
        "repair_strategy": "last_n_closed_bars",
        "bars": 500,
    }
    captured: list[dict[str, Any]] = []

    class _FakeRepo:
        async def insert_records(self, records: list[dict[str, Any]]) -> int:
            captured.extend(records)
            return len(records)

    monkeypatch.setattr(repair_audit, "SwapRepairAuditRepository", _FakeRepo)

    rows = await repair_audit.write_guard_repair_audit(
        validated_conf=validated_conf,
        guard_payloads=guard_payloads,
        dag_id="okx_swap_repair_v1",
        dag_run_id="run_20260507",
        logical_date=datetime(2026, 5, 7, tzinfo=UTC),
    )

    assert rows == 2
    assert len(captured) == 2

    ok_rec = captured[0]
    assert ok_rec["symbol"] == "BTC-USDT-SWAP"
    assert ok_rec["timeframe"] == "1H"
    assert ok_rec["strategy"] == "last_n_closed_bars"
    assert ok_rec["verified"] is True
    assert ok_rec["rows_written"] == 3
    assert ok_rec["remaining_gap_tasks"] == 0
    assert ok_rec["remaining_missing_after"] == 0
    assert ok_rec["outcome"] == "ok"
    assert ok_rec["window_start_ts_ms"] == 1_700_000_000_000
    assert ok_rec["window_end_ts_ms"] == 1_700_010_000_000

    partial_rec = captured[1]
    assert partial_rec["symbol"] == "ETH-USDT-SWAP"
    assert partial_rec["verified"] is False
    assert partial_rec["remaining_gap_tasks"] == 2
    assert partial_rec["remaining_missing_after"] == 2
    assert partial_rec["window_start_ts_ms"] == 0
    assert partial_rec["window_end_ts_ms"] == 0
