from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.application.repair.dto import RepairCommand
from src.candles.application.repair.use_cases import RunGapRepairUseCase
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
    RepairVerificationMethod,
)


@dataclass
class _FakeCoverageQuery:
    existing_timestamps: list[int]
    inserted_timestamps: list[int] = field(default_factory=list)
    count_calls: list[tuple[int, int]] = field(default_factory=list)

    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        del symbol, timeframe
        return sorted(
            ts
            for ts in self.existing_timestamps
            if start_ts_ms <= ts < end_ts_ms
        )

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        del symbol, timeframe
        self.count_calls.append((start_ts_ms, end_ts_ms))
        all_timestamps = set(self.existing_timestamps) | set(self.inserted_timestamps)
        return sum(1 for ts in all_timestamps if start_ts_ms <= ts < end_ts_ms)

    async def count_missing_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        del symbol, timeframe
        self.count_calls.append((start_ts_ms, end_ts_ms))
        all_timestamps = set(self.existing_timestamps) | set(self.inserted_timestamps)
        return sum(
            1
            for ts in range(start_ts_ms, end_ts_ms, 60_000)
            if ts not in all_timestamps
        )


@dataclass
class _FakeHistoricalSource:
    responses: list[list[dict[str, Any]]]
    calls: list[tuple[int, int]] = field(default_factory=list)

    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        del symbol, timeframe
        self.calls.append((start_ts_ms, end_ts_ms))
        if not self.responses:
            return []
        return self.responses.pop(0)


@dataclass
class _FakeRepairStore:
    coverage_query: _FakeCoverageQuery
    writes: list[list[dict[str, Any]]] = field(default_factory=list)

    async def selective_upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
    ) -> int:
        del symbol, timeframe
        self.writes.append(candles)
        self.coverage_query.inserted_timestamps.extend(
            int(candle["timestamp"]) for candle in candles
        )
        return len(candles)


def _command(*, mode: RepairExecutionMode) -> RepairCommand:
    return RepairCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=180_000,
        mode=mode,
        strategy=RepairStrategy.GAP_REPAIR,
        guardrails=RepairGuardrails(
            max_gap_tasks_per_run=10,
            max_requested_bars_per_run=100,
            max_range_days=10,
            max_fail_ratio=1.0,
        ),
        now_ts_ms=180_000,
        padding_bars=0,
    )


@pytest.mark.asyncio
async def test_gap_repair_detect_only_builds_plan_without_fetch_or_write() -> None:
    coverage_query = _FakeCoverageQuery(existing_timestamps=[0, 120_000])
    historical_source = _FakeHistoricalSource(responses=[])
    repair_store = _FakeRepairStore(coverage_query=coverage_query)
    use_case = RunGapRepairUseCase(
        coverage_query=coverage_query,
        historical_source=historical_source,
        repair_store=repair_store,
    )

    result = await use_case.run(_command(mode=RepairExecutionMode.DETECT_ONLY))

    assert result.fetch_calls == 0
    assert result.rows_written == 0
    assert result.verified is False
    assert result.remaining_gap_tasks == 1
    assert result.remaining_requested_bars == 1
    assert result.verification_method is RepairVerificationMethod.PLAN_ONLY
    assert result.plan.gap_tasks == 1
    assert result.plan.requested_bars == 1
    assert historical_source.calls == []
    assert repair_store.writes == []
    assert coverage_query.count_calls == []


@pytest.mark.asyncio
async def test_gap_repair_apply_is_not_verified_when_gap_remains_unfilled() -> None:
    coverage_query = _FakeCoverageQuery(existing_timestamps=[0, 120_000])
    historical_source = _FakeHistoricalSource(responses=[[]])
    repair_store = _FakeRepairStore(coverage_query=coverage_query)
    use_case = RunGapRepairUseCase(
        coverage_query=coverage_query,
        historical_source=historical_source,
        repair_store=repair_store,
    )

    result = await use_case.run(_command(mode=RepairExecutionMode.APPLY))

    assert result.fetch_calls == 1
    assert result.rows_written == 0
    assert result.verified is False
    assert result.remaining_gap_tasks == 1
    assert result.remaining_requested_bars == 1
    assert result.verification_method is RepairVerificationMethod.GAP_DETECTION
    assert historical_source.calls == [(60_000, 120_000)]
    assert coverage_query.count_calls == [(0, 180_000), (0, 180_000)]


@pytest.mark.asyncio
async def test_gap_repair_apply_raises_after_three_no_progress_runs_on_critical_timeframe() -> None:
    coverage_query = _FakeCoverageQuery(existing_timestamps=[0, 180_000])
    historical_source = _FakeHistoricalSource(responses=[[], [], []])
    repair_store = _FakeRepairStore(coverage_query=coverage_query)
    use_case = RunGapRepairUseCase(
        coverage_query=coverage_query,
        historical_source=historical_source,
        repair_store=repair_store,
    )
    command = _command(mode=RepairExecutionMode.APPLY)

    first = await use_case.run(command)
    second = await use_case.run(command)

    assert first.verified is False
    assert second.verified is False

    with pytest.raises(ValueError, match="no progress on critical TF 1m: 3 iterations in a row"):
        await use_case.run(command)
