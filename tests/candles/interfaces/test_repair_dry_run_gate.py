from __future__ import annotations

import pytest

from src.candles.interfaces.repair_dry_run_gate import (
    RepairDryRunGateRequest,
    run_repair_dry_run_gate,
)


class _Coverage:
    def __init__(self, timestamps: list[int]) -> None:
        self.timestamps = timestamps

    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        return [
            ts
            for ts in self.timestamps
            if start_ts_ms <= ts < end_ts_ms and symbol and timeframe
        ]


class _History:
    def __init__(self, timestamps: list[int]) -> None:
        self.timestamps = timestamps

    async def get_history_candles(
        self,
        *,
        inst_id: str,
        bar: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, int]]:
        return [
            {"ts": ts}
            for ts in self.timestamps
            if start_ts_ms <= ts < end_ts_ms and inst_id and bar
        ]


@pytest.mark.asyncio
async def test_repair_dry_run_gate_passes_when_db_matches_okx_history() -> None:
    request = RepairDryRunGateRequest(
        symbol="GRAM-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=1_000,
        end_ts_ms=4_000,
    )

    report = await run_repair_dry_run_gate(
        request=request,
        coverage=_Coverage([1_000, 2_000, 3_000]),
        history=_History([1_000, 2_000, 3_000]),
    )

    assert report.gate_passed is True
    assert report.db_row_count == 3
    assert report.okx_row_count == 3
    assert report.db_duplicate_timestamps == 0
    assert report.db_monotonic is True
    assert report.discrepancies == []


@pytest.mark.asyncio
async def test_repair_dry_run_gate_classifies_db_okx_mismatch() -> None:
    request = RepairDryRunGateRequest(
        symbol="GRAM-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=1_000,
        end_ts_ms=5_000,
    )

    report = await run_repair_dry_run_gate(
        request=request,
        coverage=_Coverage([1_000, 3_000, 3_000]),
        history=_History([1_000, 2_000, 3_000, 4_000]),
    )

    assert report.gate_passed is False
    assert report.db_duplicate_timestamps == 1
    assert report.db_monotonic is False
    assert report.discrepancies == [
        {
            "code": "db_duplicate_timestamps",
            "classification": "raw_integrity_violation",
            "count": 1,
        },
        {
            "code": "db_non_monotonic_timestamps",
            "classification": "raw_integrity_violation",
        },
        {
            "code": "db_missing_okx_timestamps",
            "classification": "repairable_raw_gap",
            "count": 2,
            "sample": [2_000, 4_000],
        },
    ]


@pytest.mark.asyncio
async def test_repair_dry_run_gate_passes_classified_repairable_and_retired_gaps() -> (
    None
):
    gram_request = RepairDryRunGateRequest(
        symbol="GRAM-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=1_000,
        end_ts_ms=5_000,
    )
    ton_request = RepairDryRunGateRequest(
        symbol="TON-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=1_000,
        end_ts_ms=5_000,
    )

    gram_report = await run_repair_dry_run_gate(
        request=gram_request,
        coverage=_Coverage([1_000, 3_000]),
        history=_History([1_000, 2_000, 3_000, 4_000]),
    )
    ton_report = await run_repair_dry_run_gate(
        request=ton_request,
        coverage=_Coverage([1_000, 2_000]),
        history=_History([]),
    )

    assert gram_report.gate_passed is True
    assert gram_report.discrepancies[0]["classification"] == "repairable_raw_gap"
    assert ton_report.gate_passed is True
    assert ton_report.discrepancies == [
        {
            "code": "okx_history_unavailable_for_db_timestamps",
            "classification": "retired_instrument_history_unavailable",
            "count": 2,
            "sample": [1_000, 2_000],
        }
    ]
