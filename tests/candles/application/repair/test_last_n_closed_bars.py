from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from src.candles.domain.okx_calendar import OKXCandleCalendar
from src.candles.domain.repair import RepairWindow
from src.core.run_context import RunContext

UTC_CAL = OKXCandleCalendar(week_anchor_ts_ms=0)


@dataclass
class CoverageStub:
    valid_sequences: list[list[int]]
    corrupted_sequences: list[list[int]]
    valid_calls: list[dict[str, Any]] = field(default_factory=list)
    corrupted_calls: list[dict[str, Any]] = field(default_factory=list)

    async def list_existing_valid_timestamps(self, **kwargs: Any) -> list[int]:
        self.valid_calls.append(kwargs)
        if len(self.valid_sequences) > 1:
            return self.valid_sequences.pop(0)
        return self.valid_sequences[0]

    async def list_corrupted_timestamps(self, **kwargs: Any) -> list[int]:
        self.corrupted_calls.append(kwargs)
        if len(self.corrupted_sequences) > 1:
            return self.corrupted_sequences.pop(0)
        return self.corrupted_sequences[0]


@dataclass
class HistoricalSourceStub:
    responses: list[list[dict[str, Any]]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def fetch_range(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        return []


@dataclass
class RepairStoreStub:
    rows_written: list[int] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def selective_upsert_candles(self, **kwargs: Any) -> int:
        self.calls.append(kwargs)
        if self.rows_written:
            return self.rows_written.pop(0)
        return len(kwargs["candles"])


def _ctx() -> RunContext:
    return RunContext(
        run_id="run-123",
        algo_version="algo-v1",
        params_hash="hash-xyz",
        created_at=datetime(2026, 5, 7, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_run_returns_ok_without_repair_when_last_n_window_is_already_valid() -> (
    None
):
    from src.candles.application.repair.last_n_closed_bars import (
        GuaranteeLastClosedBarsUseCase,
    )

    use_case = GuaranteeLastClosedBarsUseCase(
        coverage_query=CoverageStub(
            valid_sequences=[[120_000, 180_000, 240_000]],
            corrupted_sequences=[[]],
        ),
        historical_source=HistoricalSourceStub(),
        repair_store=RepairStoreStub(),
        run_context=_ctx(),
        bars=3,
        week_anchor_ts_ms=0,
        calendar=UTC_CAL,
    )

    outcome = await use_case.run("BTC-USDT-SWAP", "1m", 300_000)

    assert outcome.status == "ok"
    assert outcome.unresolved_timestamps == []
    assert outcome.affected_recalc_range is None
    assert outcome.corrupted_count == 0
    assert outcome.repaired_count == 0
    assert outcome.run_id == "run-123"
    assert outcome.algo_version == "algo-v1"
    assert outcome.params_hash == "hash-xyz"


@pytest.mark.asyncio
async def test_run_repairs_missing_and_corrupted_timestamps_then_verifies_green() -> (
    None
):
    from src.candles.application.repair.last_n_closed_bars import (
        GuaranteeLastClosedBarsUseCase,
    )

    coverage = CoverageStub(
        valid_sequences=[[120_000], [120_000, 180_000, 240_000]],
        corrupted_sequences=[[180_000], []],
    )
    historical = HistoricalSourceStub(
        responses=[
            [
                {
                    "ts": 180_000,
                    "open": 10,
                    "high": 12,
                    "low": 9,
                    "close": 11,
                    "volume": 100,
                },
                {
                    "ts": 240_000,
                    "open": 11,
                    "high": 13,
                    "low": 10,
                    "close": 12,
                    "volume": 110,
                },
            ]
        ]
    )
    store = RepairStoreStub(rows_written=[2])
    use_case = GuaranteeLastClosedBarsUseCase(
        coverage_query=coverage,
        historical_source=historical,
        repair_store=store,
        run_context=_ctx(),
        bars=3,
        week_anchor_ts_ms=0,
        calendar=UTC_CAL,
    )

    outcome = await use_case.run("BTC-USDT-SWAP", "1m", 300_000)

    assert outcome.status == "ok"
    assert outcome.unresolved_timestamps == []
    assert outcome.affected_recalc_range == (180_000, 300_000)
    assert outcome.corrupted_count == 1
    assert outcome.repaired_count == 2
    assert historical.calls == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "start_ts_ms": 180_000,
            "end_ts_ms": 300_000,
        }
    ]
    assert [row["timestamp"] for row in store.calls[0]["candles"]] == [180_000, 240_000]
    assert store.calls[0]["window"] == RepairWindow(180_000, 300_000)


@pytest.mark.asyncio
async def test_run_returns_blocked_when_no_progress_was_made() -> None:
    from src.candles.application.repair.last_n_closed_bars import (
        GuaranteeLastClosedBarsUseCase,
    )

    coverage = CoverageStub(
        valid_sequences=[[120_000], [120_000]],
        corrupted_sequences=[[], []],
    )
    use_case = GuaranteeLastClosedBarsUseCase(
        coverage_query=coverage,
        historical_source=HistoricalSourceStub(responses=[[]]),
        repair_store=RepairStoreStub(rows_written=[0]),
        run_context=_ctx(),
        bars=3,
        week_anchor_ts_ms=0,
        calendar=UTC_CAL,
    )

    outcome = await use_case.run("BTC-USDT-SWAP", "1m", 300_000)

    assert outcome.status == "blocked"
    assert outcome.unresolved_timestamps == [180_000, 240_000]
    assert outcome.affected_recalc_range is None
    assert outcome.repaired_count == 0


@pytest.mark.asyncio
async def test_run_returns_partial_when_only_subset_of_window_is_fixed() -> None:
    from src.candles.application.repair.last_n_closed_bars import (
        GuaranteeLastClosedBarsUseCase,
    )

    coverage = CoverageStub(
        valid_sequences=[[120_000], [120_000, 180_000]],
        corrupted_sequences=[[], []],
    )
    historical = HistoricalSourceStub(
        responses=[
            [
                {
                    "ts": 180_000,
                    "open": 10,
                    "high": 12,
                    "low": 9,
                    "close": 11,
                    "volume": 100,
                }
            ]
        ]
    )
    use_case = GuaranteeLastClosedBarsUseCase(
        coverage_query=coverage,
        historical_source=historical,
        repair_store=RepairStoreStub(rows_written=[1]),
        run_context=_ctx(),
        bars=3,
        week_anchor_ts_ms=0,
        calendar=UTC_CAL,
    )

    outcome = await use_case.run("BTC-USDT-SWAP", "1m", 300_000)

    assert outcome.status == "partial"
    assert outcome.unresolved_timestamps == [240_000]
    assert outcome.affected_recalc_range is None
    assert outcome.repaired_count == 1
