from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.application.repair.dto import RepairCommand
from src.candles.application.repair.use_cases import (
    RunGapRepairUseCase,
    RunHistoricalBackfillUseCase,
)
from src.candles.domain.repair import (
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
    RepairVerificationMethod,
)


@dataclass
class CoverageQueryStub:
    timestamps: list[int] = field(default_factory=list)
    count_result: int = 0
    list_calls: list[dict[str, Any]] = field(default_factory=list)
    count_calls: list[dict[str, Any]] = field(default_factory=list)
    missing_count_calls: list[dict[str, Any]] = field(default_factory=list)

    async def list_timestamps(self, **kwargs: Any) -> list[int]:
        self.list_calls.append(kwargs)
        return self.timestamps

    async def count_candles(self, **kwargs: Any) -> int:
        self.count_calls.append(kwargs)
        return self.count_result

    async def count_missing_timestamps(self, **kwargs: Any) -> int:
        self.missing_count_calls.append(kwargs)
        start_ts_ms = int(kwargs["start_ts_ms"])
        end_ts_ms = int(kwargs["end_ts_ms"])
        existing = {ts for ts in self.timestamps if start_ts_ms <= ts < end_ts_ms}
        return sum(
            1 for ts in range(start_ts_ms, end_ts_ms, 60_000) if ts not in existing
        )


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
    rows_written_per_call: list[int] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    coverage: CoverageQueryStub | None = None

    async def selective_upsert_candles(self, **kwargs: Any) -> int:
        self.calls.append(kwargs)
        if self.coverage is not None:
            for candle in kwargs["candles"]:
                timestamp = int(candle["timestamp"])
                if timestamp not in self.coverage.timestamps:
                    self.coverage.timestamps.append(timestamp)
        if self.rows_written_per_call:
            return self.rows_written_per_call.pop(0)
        return 0


@dataclass
class TelemetryStub:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        return None

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        return None

    def event(self, name: str, **payload: Any) -> None:
        self.events.append((name, payload))


def _guardrails(*, max_fail_ratio: float = 1.0) -> RepairGuardrails:
    return RepairGuardrails(
        max_gap_tasks_per_run=100,
        max_requested_bars_per_run=1_000,
        max_range_days=365,
        max_fail_ratio=max_fail_ratio,
    )


def _command(
    *,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    start_ts_ms: int = 0,
    end_ts_ms: int = 5 * 60_000,
    now_ts_ms: int = 5 * 60_000,
    padding_bars: int = 0,
    guardrails: RepairGuardrails | None = None,
) -> RepairCommand:
    return RepairCommand(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        mode=mode,
        strategy=strategy,
        guardrails=guardrails or _guardrails(),
        now_ts_ms=now_ts_ms,
        padding_bars=padding_bars,
    )


@pytest.mark.asyncio
async def test_gap_repair_detect_only_builds_plan_without_fetch_or_write() -> None:
    coverage = CoverageQueryStub(timestamps=[0, 60_000, 3 * 60_000, 4 * 60_000])
    use_case = RunGapRepairUseCase(
        coverage_query=coverage,
        historical_source=HistoricalSourceStub(),
        repair_store=RepairStoreStub(),
    )

    result = await use_case.run(
        _command(mode=RepairExecutionMode.DETECT_ONLY, strategy=RepairStrategy.GAP_REPAIR)
    )

    assert result.fetch_calls == 0
    assert result.rows_written == 0
    assert result.verified is False
    assert result.remaining_gap_tasks == 1
    assert result.remaining_requested_bars == 1
    assert result.verification_method is RepairVerificationMethod.PLAN_ONLY
    assert result.watermark_updated is False
    assert result.plan.requested_bars == 1
    assert [(task.start_ts_ms, task.end_ts_ms) for task in result.plan.tasks] == [
        (2 * 60_000, 3 * 60_000),
    ]
    assert len(coverage.list_calls) == 1
    assert coverage.count_calls == []


@pytest.mark.asyncio
async def test_backfill_dry_run_plans_whole_closed_window() -> None:
    use_case = RunHistoricalBackfillUseCase(
        coverage_query=CoverageQueryStub(),
        historical_source=HistoricalSourceStub(),
        repair_store=RepairStoreStub(),
    )

    result = await use_case.run(
        _command(mode=RepairExecutionMode.DRY_RUN, strategy=RepairStrategy.BACKFILL)
    )

    assert result.fetch_calls == 0
    assert result.rows_written == 0
    assert result.remaining_gap_tasks == 1
    assert result.remaining_requested_bars == 5
    assert result.verification_method is RepairVerificationMethod.PLAN_ONLY
    assert result.plan.requested_bars == 5
    assert len(result.plan.tasks) == 1
    assert result.plan.tasks[0].start_ts_ms == 0
    assert result.plan.tasks[0].end_ts_ms == 5 * 60_000


@pytest.mark.asyncio
async def test_backfill_apply_fetches_full_window_and_writes_valid_rows() -> None:
    coverage = CoverageQueryStub(count_result=5)
    historical = HistoricalSourceStub(
        responses=[
            [
                {"ts": 0, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10},
                {"ts": 60_000, "open": 2, "high": 3, "low": 1, "close": 2, "volume": 11},
                {"ts": 2 * 60_000, "open": 3, "high": 4, "low": 2, "close": 3, "volume": 12},
                {"ts": 3 * 60_000, "open": 4, "high": 5, "low": 3, "close": 4, "volume": 13},
                {"ts": 4 * 60_000, "open": 5, "high": 6, "low": 4, "close": 5, "volume": 14},
            ]
        ]
    )
    store = RepairStoreStub(rows_written_per_call=[5])
    store.coverage = coverage
    use_case = RunHistoricalBackfillUseCase(
        coverage_query=coverage,
        historical_source=historical,
        repair_store=store,
    )

    result = await use_case.run(
        _command(mode=RepairExecutionMode.APPLY, strategy=RepairStrategy.BACKFILL)
    )

    assert result.fetch_calls == 1
    assert result.rows_written == 5
    assert result.verified is True
    assert result.remaining_gap_tasks == 0
    assert result.remaining_requested_bars == 0
    assert result.verification_method is RepairVerificationMethod.GAP_DETECTION
    assert historical.calls == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "start_ts_ms": 0,
            "end_ts_ms": 5 * 60_000,
        }
    ]
    assert coverage.count_calls == []
    assert [row["timestamp"] for row in store.calls[0]["candles"]] == [
        0,
        60_000,
        2 * 60_000,
        3 * 60_000,
        4 * 60_000,
    ]


@pytest.mark.asyncio
async def test_apply_gap_repair_filters_open_bar_and_emits_telemetry() -> None:
    coverage = CoverageQueryStub(
        timestamps=[0, 60_000, 4 * 60_000],
        count_result=5,
    )
    historical = HistoricalSourceStub(
        responses=[
            [
                {"ts": 2 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10},
                {"ts": 3 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 11},
                {"ts": 4 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 12},
            ]
        ]
    )
    store = RepairStoreStub(rows_written_per_call=[2])
    store.coverage = coverage
    telemetry = TelemetryStub()
    use_case = RunGapRepairUseCase(
        coverage_query=coverage,
        historical_source=historical,
        repair_store=store,
        telemetry=telemetry,
    )

    result = await use_case.run(
        _command(mode=RepairExecutionMode.APPLY, strategy=RepairStrategy.GAP_REPAIR)
    )

    assert result.fetch_calls == 1
    assert result.rows_written == 2
    assert result.verified is True
    assert result.remaining_gap_tasks == 0
    assert result.remaining_requested_bars == 0
    assert result.verification_method is RepairVerificationMethod.GAP_DETECTION
    assert result.watermark_updated is False
    assert len(store.calls) == 1
    assert [row["timestamp"] for row in store.calls[0]["candles"]] == [2 * 60_000, 3 * 60_000]
    assert coverage.count_calls == []
    assert telemetry.events[0][0] == "candles.repair.completed"


@pytest.mark.asyncio
async def test_apply_backfill_writes_full_window_and_verifies_coverage() -> None:
    coverage = CoverageQueryStub(count_result=5)
    historical = HistoricalSourceStub(
        responses=[
            [
                {"ts": 0, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10},
                {"ts": 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 11},
                {"ts": 2 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 12},
                {"ts": 3 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 13},
                {"ts": 4 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 14},
            ]
        ]
    )
    store = RepairStoreStub(rows_written_per_call=[5])
    store.coverage = coverage
    use_case = RunHistoricalBackfillUseCase(
        coverage_query=coverage,
        historical_source=historical,
        repair_store=store,
    )

    result = await use_case.run(
        _command(mode=RepairExecutionMode.APPLY, strategy=RepairStrategy.BACKFILL)
    )

    assert result.fetch_calls == 1
    assert result.rows_written == 5
    assert result.verified is True
    assert result.remaining_gap_tasks == 0
    assert result.remaining_requested_bars == 0
    assert result.verification_method is RepairVerificationMethod.GAP_DETECTION
    assert result.plan.requested_bars == 5
    assert coverage.count_calls == []
    assert [row["timestamp"] for row in store.calls[0]["candles"]] == [
        0,
        60_000,
        2 * 60_000,
        3 * 60_000,
        4 * 60_000,
    ]


@pytest.mark.asyncio
async def test_apply_rejects_guardrail_violation_before_write() -> None:
    command = _command(
        mode=RepairExecutionMode.APPLY,
        strategy=RepairStrategy.GAP_REPAIR,
        guardrails=RepairGuardrails(
            max_gap_tasks_per_run=0,
            max_requested_bars_per_run=1_000,
            max_range_days=365,
            max_fail_ratio=1.0,
        ),
    )
    historical = HistoricalSourceStub()
    store = RepairStoreStub()
    use_case = RunGapRepairUseCase(
        coverage_query=CoverageQueryStub(timestamps=[]),
        historical_source=historical,
        repair_store=store,
    )

    with pytest.raises(ValueError, match="apply blocked by guardrails"):
        await use_case.run(command)

    assert historical.calls == []
    assert store.calls == []


@pytest.mark.asyncio
async def test_apply_marks_result_unverified_when_window_still_has_gaps() -> None:
    coverage = CoverageQueryStub(
        timestamps=[0, 60_000, 4 * 60_000],
        count_result=4,
    )
    historical = HistoricalSourceStub(
        responses=[
            [
                {"ts": 2 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10},
            ]
        ]
    )
    store = RepairStoreStub(rows_written_per_call=[1])
    store.coverage = coverage
    use_case = RunGapRepairUseCase(
        coverage_query=coverage,
        historical_source=historical,
        repair_store=store,
    )

    result = await use_case.run(
        _command(mode=RepairExecutionMode.APPLY, strategy=RepairStrategy.GAP_REPAIR)
    )

    assert result.rows_written == 1
    assert result.verified is False
    assert result.remaining_gap_tasks == 1
    assert result.remaining_requested_bars == 1
    assert result.verification_method is RepairVerificationMethod.GAP_DETECTION
    assert coverage.count_calls == []


@pytest.mark.asyncio
async def test_apply_raises_when_fail_ratio_exceeds_limit() -> None:
    coverage = CoverageQueryStub(timestamps=[0], count_result=1)
    historical = HistoricalSourceStub(
        responses=[
            [
                {"ts": 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10},
                {"ts": 2 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 11},
                {"ts": 3 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 12},
                {"ts": 4 * 60_000, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 13},
            ]
        ]
    )
    store = RepairStoreStub(rows_written_per_call=[1])
    use_case = RunGapRepairUseCase(
        coverage_query=coverage,
        historical_source=historical,
        repair_store=store,
    )

    with pytest.raises(ValueError, match="apply exceeded max_fail_ratio"):
        await use_case.run(
            _command(
                mode=RepairExecutionMode.APPLY,
                strategy=RepairStrategy.GAP_REPAIR,
                guardrails=_guardrails(max_fail_ratio=0.2),
            )
        )
