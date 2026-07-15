from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.candles.application.repair.dto import (
    RepairCommand,
    RepairResult,
)
from src.candles.application.repair.use_cases import (
    RunGapRepairUseCase,
    RunHistoricalBackfillUseCase,
)
from src.candles.domain.okx_calendar import OKXCandleCalendar
from src.candles.domain.repair import (
    BackfillPlan,
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
)

UTC_CAL = OKXCandleCalendar(week_anchor_ts_ms=0)


@dataclass
class _CoverageQueryStub:
    timestamps: list[int]
    verified_count: int | None = None

    def __post_init__(self) -> None:
        self.list_calls = 0
        self.count_calls = 0
        self.missing_calls = 0

    async def list_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[int]:
        self.list_calls += 1
        if self.verified_count is not None and self.missing_calls > 1:
            return list(range(start_ts_ms, end_ts_ms, 60_000))[: self.verified_count]
        return list(self.timestamps)

    async def count_missing_timestamps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        del symbol, timeframe
        self.missing_calls += 1
        expected = len(range(start_ts_ms, end_ts_ms, 60_000))
        if self.verified_count is not None and self.missing_calls > 1:
            return max(expected - self.verified_count, 0)
        return max(expected - len(self.timestamps), 0)

    async def count_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> int:
        self.count_calls += 1
        return (
            self.verified_count
            if self.verified_count is not None
            else len(self.timestamps)
        )


@dataclass
class _HistoricalSourceStub:
    candles: list[dict[str, Any]]

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_ts_ms": start_ts_ms,
                "end_ts_ms": end_ts_ms,
            }
        )
        return list(self.candles)


class _RepairStoreSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def selective_upsert_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        **kwargs: Any,
    ) -> int:
        del kwargs
        self.calls.append(
            {"symbol": symbol, "timeframe": timeframe, "candles": list(candles)}
        )
        return len(candles)


class _TelemetrySpy:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        return None

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        return None

    def event(self, name: str, **payload: Any) -> None:
        self.events.append((name, payload))


def _command(*, mode: RepairExecutionMode, strategy: RepairStrategy) -> RepairCommand:
    return RepairCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=0,
        end_ts_ms=1_140_000,
        mode=mode,
        strategy=strategy,
        guardrails=RepairGuardrails(
            max_gap_tasks_per_run=10,
            max_requested_bars_per_run=100,
            max_range_days=7,
            max_fail_ratio=0.5,
        ),
        now_ts_ms=1_200_000,
    )


@pytest.mark.asyncio
async def test_gap_repair_detect_only_does_not_fetch_or_write() -> None:
    query = _CoverageQueryStub(timestamps=[0, 60_000])
    source = _HistoricalSourceStub(candles=[])
    store = _RepairStoreSpy()

    result = await RunGapRepairUseCase(
        coverage_query=query,
        historical_source=source,
        repair_store=store,
        calendar=UTC_CAL,
    ).run(
        _command(
            mode=RepairExecutionMode.DETECT_ONLY, strategy=RepairStrategy.GAP_REPAIR
        )
    )

    assert result.mode is RepairExecutionMode.DETECT_ONLY
    assert result.fetch_calls == 0
    assert result.rows_written == 0
    assert source.calls == []
    assert store.calls == []


@pytest.mark.asyncio
async def test_backfill_dry_run_builds_plan_without_write() -> None:
    query = _CoverageQueryStub(timestamps=[])
    source = _HistoricalSourceStub(candles=[])
    store = _RepairStoreSpy()

    result = await RunHistoricalBackfillUseCase(
        coverage_query=query,
        historical_source=source,
        repair_store=store,
        calendar=UTC_CAL,
    ).run(_command(mode=RepairExecutionMode.DRY_RUN, strategy=RepairStrategy.BACKFILL))

    assert result.mode is RepairExecutionMode.DRY_RUN
    assert result.plan.requested_bars == 19
    assert isinstance(result.plan, BackfillPlan)
    assert result.fetch_calls == 0
    assert store.calls == []
    assert result.watermark_updated is False


@pytest.mark.asyncio
async def test_apply_fetches_upserts_and_verifies() -> None:
    query = _CoverageQueryStub(timestamps=[], verified_count=2)
    source = _HistoricalSourceStub(
        candles=[
            {
                "ts": -60_000,
                "open": 0.0,
                "high": 0.0,
                "low": 0.0,
                "close": 0.0,
                "volume": 0.0,
                "volCcy": None,
                "volUsd": None,
            },
            {
                "ts": 0,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
                "volCcy": None,
                "volUsd": None,
            },
            {
                "ts": 60_000,
                "open": 1.5,
                "high": 2.5,
                "low": 1.0,
                "close": 2.0,
                "volume": 11.0,
                "volCcy": None,
                "volUsd": None,
            },
            {
                "ts": 120_000,
                "open": 3.0,
                "high": 3.0,
                "low": 3.0,
                "close": 3.0,
                "volume": 0.0,
                "volCcy": None,
                "volUsd": None,
            },
        ]
    )
    store = _RepairStoreSpy()
    telemetry = _TelemetrySpy()

    result = await RunHistoricalBackfillUseCase(
        coverage_query=query,
        historical_source=source,
        repair_store=store,
        telemetry=telemetry,
        calendar=UTC_CAL,
    ).run(
        RepairCommand(
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            start_ts_ms=0,
            end_ts_ms=120_000,
            mode=RepairExecutionMode.APPLY,
            strategy=RepairStrategy.BACKFILL,
            guardrails=RepairGuardrails(
                max_gap_tasks_per_run=10,
                max_requested_bars_per_run=100,
                max_range_days=7,
                max_fail_ratio=0.5,
            ),
            now_ts_ms=180_000,
            padding_bars=1,
        )
    )

    assert isinstance(result, RepairResult)
    assert result.rows_written == 2
    assert result.fetch_calls == 1
    assert result.verified is True
    assert result.watermark_updated is False
    assert len(store.calls) == 1
    assert [row["timestamp"] for row in store.calls[0]["candles"]] == [0, 60_000]
    assert telemetry.events[-1][0] == "candles.repair.completed"


@pytest.mark.asyncio
async def test_apply_fails_fast_when_guardrails_are_exceeded() -> None:
    command = _command(mode=RepairExecutionMode.APPLY, strategy=RepairStrategy.BACKFILL)
    command = RepairCommand(
        **{
            **command.__dict__,
            "guardrails": RepairGuardrails(
                max_gap_tasks_per_run=10,
                max_requested_bars_per_run=1,
                max_range_days=7,
                max_fail_ratio=0.5,
            ),
        }
    )

    with pytest.raises(ValueError, match="max_requested_bars_per_run"):
        await RunHistoricalBackfillUseCase(
            coverage_query=_CoverageQueryStub(timestamps=[]),
            historical_source=_HistoricalSourceStub(candles=[]),
            repair_store=_RepairStoreSpy(),
            calendar=UTC_CAL,
        ).run(command)
