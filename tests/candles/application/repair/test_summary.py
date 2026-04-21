from __future__ import annotations

import pytest

from src.candles.application.repair.summary import (
    RepairSummary,
    build_noop_repair_summary,
    merge_repair_summaries,
)
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairOutcome,
    RepairStrategy,
    RepairVerificationMethod,
    RepairWindow,
)


def _summary(
    *,
    symbol: str = "BTC-USDT-SWAP",
    timeframe: str = "1m",
    remaining_gap_tasks: int = 0,
    remaining_requested_bars: int = 0,
) -> RepairSummary:
    return RepairSummary(
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        symbol=symbol,
        timeframe=timeframe,
        window=RepairWindow(start_ts_ms=10, end_ts_ms=20),
        gap_tasks=1,
        requested_bars=1,
        remaining_gap_tasks=remaining_gap_tasks,
        remaining_requested_bars=remaining_requested_bars,
        verification_method=RepairVerificationMethod.GAP_DETECTION,
        rows_written=1,
        fetch_calls=1,
        verified=remaining_gap_tasks == 0 and remaining_requested_bars == 0,
        padding_bars=0,
    )


def test_merge_repair_summaries_rejects_mismatched_symbol() -> None:
    with pytest.raises(ValueError, match="requires identical symbol"):
        merge_repair_summaries(
            validated={"symbol": "BTC-USDT-SWAP", "repair_strategy": "gap-repair", "padding_bars": 0},
            timeframe="1m",
            summaries=[
                _summary(symbol="BTC-USDT-SWAP"),
                _summary(symbol="ETH-USDT-SWAP"),
            ],
            closed_until_ts_ms=20,
        )


def test_merge_repair_summaries_marks_partial_auto_apply() -> None:
    summary = merge_repair_summaries(
        validated={"symbol": "BTC-USDT-SWAP", "repair_strategy": "gap-repair", "padding_bars": 0},
        timeframe="1m",
        summaries=[
            _summary(remaining_gap_tasks=1, remaining_requested_bars=1),
            _summary(remaining_gap_tasks=1, remaining_requested_bars=1),
        ],
        closed_until_ts_ms=20,
    )

    assert summary.remaining_gap_tasks == 1
    assert summary.remaining_requested_bars == 1
    assert summary.auto_apply_incomplete is True
    assert summary.to_dict()["auto_apply_incomplete"] is True


def test_repair_summary_from_mapping_infers_partial_auto_apply() -> None:
    summary = RepairSummary.from_mapping(
        {
            "mode": "apply",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "window": {"start_ts_ms": 10, "end_ts_ms": 20},
            "gap_tasks": 1,
            "requested_bars": 1,
            "remaining_gap_tasks": 1,
            "remaining_requested_bars": 1,
            "verification_method": "gap-detection",
            "rows_written": 1,
            "fetch_calls": 1,
            "verified": False,
            "padding_bars": 0,
            "auto_apply_incomplete": False,
        }
    )

    assert summary.auto_apply_incomplete is True


def test_repair_summary_from_result_marks_partial_auto_apply() -> None:
    result = type(
        "RepairResultStub",
        (),
        {
            "mode": RepairExecutionMode.APPLY,
            "strategy": RepairStrategy.GAP_REPAIR,
            "plan": type(
                "RepairPlanStub",
                (),
                {
                    "symbol": "BTC-USDT-SWAP",
                    "timeframe": "1m",
                    "window": RepairWindow(start_ts_ms=10, end_ts_ms=20),
                    "gap_tasks": 1,
                    "requested_bars": 1,
                },
            )(),
            "fetch_calls": 1,
            "rows_written": 1,
            "verified": False,
            "remaining_gap_tasks": 1,
            "remaining_requested_bars": 1,
            "verification_method": RepairVerificationMethod.GAP_DETECTION,
            "watermark_updated": False,
        },
    )()

    summary = RepairSummary.from_result(result, padding_bars=0)

    assert summary.auto_apply_incomplete is True
    assert summary.to_dict()["auto_apply_incomplete"] is True


def test_summary_round_trip_includes_new_fields() -> None:
    original = RepairSummary(
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window=RepairWindow(start_ts_ms=0, end_ts_ms=180_000),
        gap_tasks=1,
        requested_bars=3,
        remaining_gap_tasks=0,
        remaining_requested_bars=0,
        verification_method=RepairVerificationMethod.GAP_DETECTION,
        rows_written=2,
        fetch_calls=1,
        verified=True,
        padding_bars=0,
        received_bars=3,
        remaining_missing_before=3,
        remaining_missing_after=1,
        progress=2,
        api_fill_ratio=1.0,
        write_success_ratio=2 / 3,
        outcome=RepairOutcome.PARTIAL,
    )

    payload = original.to_dict()
    assert payload["received_bars"] == 3
    assert payload["remaining_missing_before"] == 3
    assert payload["remaining_missing_after"] == 1
    assert payload["progress"] == 2
    assert payload["api_fill_ratio"] == 1.0
    assert payload["write_success_ratio"] == pytest.approx(2 / 3)
    assert payload["outcome"] == "partial"

    restored = RepairSummary.from_mapping(payload)
    assert restored.received_bars == 3
    assert restored.remaining_missing_before == 3
    assert restored.remaining_missing_after == 1
    assert restored.progress == 2
    assert restored.api_fill_ratio == 1.0
    assert restored.write_success_ratio == pytest.approx(2 / 3)
    assert restored.outcome is RepairOutcome.PARTIAL


def test_merge_two_partial_summaries() -> None:
    first = RepairSummary(
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window=RepairWindow(start_ts_ms=0, end_ts_ms=60_000),
        gap_tasks=1,
        requested_bars=2,
        remaining_gap_tasks=1,
        remaining_requested_bars=1,
        verification_method=RepairVerificationMethod.GAP_DETECTION,
        rows_written=1,
        fetch_calls=1,
        verified=False,
        padding_bars=0,
        received_bars=1,
        remaining_missing_before=3,
        remaining_missing_after=2,
        progress=1,
        api_fill_ratio=0.5,
        write_success_ratio=1.0,
        outcome=RepairOutcome.PARTIAL,
    )
    second = RepairSummary(
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        window=RepairWindow(start_ts_ms=60_000, end_ts_ms=120_000),
        gap_tasks=1,
        requested_bars=2,
        remaining_gap_tasks=1,
        remaining_requested_bars=1,
        verification_method=RepairVerificationMethod.GAP_DETECTION,
        rows_written=1,
        fetch_calls=1,
        verified=False,
        padding_bars=0,
        received_bars=1,
        remaining_missing_before=2,
        remaining_missing_after=1,
        progress=1,
        api_fill_ratio=0.5,
        write_success_ratio=1.0,
        outcome=RepairOutcome.PARTIAL,
    )

    merged = merge_repair_summaries(
        validated={"symbol": "BTC-USDT-SWAP", "repair_strategy": "gap-repair", "padding_bars": 0},
        timeframe="1m",
        summaries=[first, second],
        closed_until_ts_ms=120_000,
    )

    assert merged.outcome is RepairOutcome.PARTIAL
    assert merged.received_bars == 2
    assert merged.remaining_missing_before == 3
    assert merged.remaining_missing_after == 1
    assert merged.progress == 2
    assert merged.requested_bars == 4
    assert merged.rows_written == 2
    assert merged.api_fill_ratio == pytest.approx(2 / 4)
    assert merged.write_success_ratio == pytest.approx(2 / 2)


def test_noop_summary_outcome_is_success() -> None:
    summary = build_noop_repair_summary(
        validated={
            "symbol": "BTC-USDT-SWAP",
            "repair_strategy": "gap-repair",
            "padding_bars": 0,
        },
        timeframe="1m",
        closed_until_ts_ms=180_000,
    )

    assert summary.outcome is RepairOutcome.SUCCESS
    assert summary.received_bars == 0
    assert summary.remaining_missing_before == 0
    assert summary.remaining_missing_after == 0
    assert summary.progress == 0
    assert summary.api_fill_ratio == 0.0
    assert summary.write_success_ratio == 0.0
    assert summary.verified is True
