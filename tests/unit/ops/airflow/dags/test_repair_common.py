from __future__ import annotations

import pytest

from ops.airflow.dags._common.repair import normalize_swap_repair_summary_payloads
from src.candles.application.repair.summary import RepairSummary
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairStrategy,
    RepairVerificationMethod,
    RepairWindow,
)


def test_normalize_swap_repair_summary_payloads_coerces_mixed_inputs() -> None:
    payloads = normalize_swap_repair_summary_payloads(
        [
            {
                "mode": "apply",
                "strategy": "gap-repair",
                "symbol": "BTC-USDT-SWAP",
                "timeframe": "1m",
                "window": {"start_ts_ms": 10, "end_ts_ms": 20},
                "gap_tasks": 2,
                "requested_bars": 4,
                "remaining_gap_tasks": 1,
                "remaining_requested_bars": 0,
                "verification_method": "gap-detection",
                "rows_written": 4,
                "fetch_calls": 1,
                "verified": False,
                "padding_bars": 0,
                "guardrail_violations": [],
                "watermark_updated": False,
                "auto_apply_incomplete": False,
            },
            RepairSummary(
                mode=RepairExecutionMode.DETECT_ONLY,
                strategy=RepairStrategy.GAP_REPAIR,
                symbol="BTC-USDT-SWAP",
                timeframe="1H",
                window=RepairWindow(start_ts_ms=30, end_ts_ms=40),
                gap_tasks=0,
                requested_bars=0,
                remaining_gap_tasks=0,
                remaining_requested_bars=0,
                verification_method=RepairVerificationMethod.PLAN_ONLY,
                rows_written=0,
                fetch_calls=0,
                verified=False,
                padding_bars=0,
            ),
        ]
    )

    assert payloads == [
        {
            "mode": "apply",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "window": {"start_ts_ms": 10, "end_ts_ms": 20},
            "gap_tasks": 2,
            "requested_bars": 4,
            "remaining_gap_tasks": 1,
            "remaining_requested_bars": 0,
            "verification_method": "gap-detection",
            "rows_written": 4,
            "fetch_calls": 1,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
            "auto_apply_incomplete": True,
        },
        {
            "mode": "detect-only",
            "strategy": "gap-repair",
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1H",
            "window": {"start_ts_ms": 30, "end_ts_ms": 40},
            "gap_tasks": 0,
            "requested_bars": 0,
            "remaining_gap_tasks": 0,
            "remaining_requested_bars": 0,
            "verification_method": "plan-only",
            "rows_written": 0,
            "fetch_calls": 0,
            "verified": False,
            "padding_bars": 0,
            "guardrail_violations": [],
            "watermark_updated": False,
        },
    ]


def test_normalize_swap_repair_summary_payloads_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="requires validated summary payloads"):
        normalize_swap_repair_summary_payloads([])
