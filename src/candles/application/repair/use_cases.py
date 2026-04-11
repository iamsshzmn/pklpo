from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.candles.domain.repair import (
    BackfillPlan,
    RepairExecutionMode,
    RepairPlan,
    RepairStrategy,
    RepairWindow,
    clamp_window_to_closed_bars,
    count_expected_bars,
    detect_gap_tasks,
    sanitize_repair_candle,
    validate_repair_candles,
)
from src.candles.domain.repair_timeframes import window_padding

from .dto import RepairCommand, RepairResult

if TYPE_CHECKING:
    from .ports import (
        CandleCoverageQueryPort,
        HistoricalCandleSourcePort,
        RepairCandleStorePort,
        TelemetryPort,
    )


class _NullTelemetry:
    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        return None

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        return None

    def event(self, name: str, **payload: Any) -> None:
        return None


class _BaseRepairUseCase:
    def __init__(
        self,
        *,
        coverage_query: CandleCoverageQueryPort,
        historical_source: HistoricalCandleSourcePort,
        repair_store: RepairCandleStorePort,
        telemetry: TelemetryPort | None = None,
    ) -> None:
        self._coverage_query = coverage_query
        self._historical_source = historical_source
        self._repair_store = repair_store
        self._telemetry = telemetry or _NullTelemetry()

    async def run(self, command: RepairCommand) -> RepairResult:
        plan = await self._build_plan(command)
        violations = command.guardrails.check(plan)
        if violations and command.mode is RepairExecutionMode.APPLY:
            codes = ", ".join(violation.code for violation in violations)
            raise ValueError(f"apply blocked by guardrails: {codes}")

        if command.mode is RepairExecutionMode.DETECT_ONLY:
            return RepairResult(
                mode=command.mode,
                strategy=command.strategy,
                plan=plan,
                fetch_calls=0,
                rows_written=0,
                verified=False,
                watermark_updated=False,
            )

        if command.mode is RepairExecutionMode.DRY_RUN:
            return RepairResult(
                mode=command.mode,
                strategy=command.strategy,
                plan=plan,
                fetch_calls=0,
                rows_written=0,
                verified=False,
                watermark_updated=False,
            )

        rows_written = 0
        fetch_calls = 0
        total_requested = 0
        total_missing = max(plan.requested_bars, 1)

        for task in plan.tasks:
            padding_ms = window_padding(plan.timeframe, command.padding_bars)
            candles = await self._historical_source.fetch_range(
                symbol=plan.symbol,
                timeframe=plan.timeframe,
                start_ts_ms=max(plan.window.start_ts_ms, task.start_ts_ms - padding_ms),
                end_ts_ms=min(plan.window.end_ts_ms, task.end_ts_ms + padding_ms),
            )
            fetch_calls += 1
            total_requested += task.missing_bars
            valid_rows = validate_repair_candles(
                candles=candles,
                task_window=RepairWindow(task.start_ts_ms, task.end_ts_ms),
                closed_until_ts_ms=plan.window.end_ts_ms,
            )
            validated = self._sanitize_candles(valid_rows)
            rows_written += await self._repair_store.selective_upsert_candles(
                symbol=plan.symbol,
                timeframe=plan.timeframe,
                candles=validated,
            )

        verified_count = await self._coverage_query.count_candles(
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            start_ts_ms=plan.window.start_ts_ms,
            end_ts_ms=plan.window.end_ts_ms,
        )
        verified = verified_count >= count_expected_bars(
            window=plan.window,
            timeframe=plan.timeframe,
        )
        fail_ratio = 0.0 if total_requested == 0 else max(total_requested - rows_written, 0) / total_missing
        if fail_ratio > command.guardrails.max_fail_ratio:
            raise ValueError("apply exceeded max_fail_ratio")

        self._telemetry.event(
            "candles.repair.completed",
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            strategy=plan.strategy.value,
            rows_written=rows_written,
            fetch_calls=fetch_calls,
            verified=verified,
        )
        return RepairResult(
            mode=command.mode,
            strategy=command.strategy,
            plan=plan,
            fetch_calls=fetch_calls,
            rows_written=rows_written,
            verified=verified,
            watermark_updated=False,
        )

    async def _build_plan(self, command: RepairCommand) -> RepairPlan:
        raise NotImplementedError

    def _sanitize_candles(self, candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fetched_at = datetime.now(UTC)
        return [sanitize_repair_candle(candle, fetched_at=fetched_at) for candle in candles]

    def _normalized_window(self, command: RepairCommand) -> RepairWindow:
        return clamp_window_to_closed_bars(
            window=RepairWindow(command.start_ts_ms, command.end_ts_ms),
            timeframe=command.timeframe,
            now_ts_ms=command.now_ts_ms,
        )


class RunGapRepairUseCase(_BaseRepairUseCase):
    async def _build_plan(self, command: RepairCommand) -> RepairPlan:
        window = self._normalized_window(command)
        timestamps = await self._coverage_query.list_timestamps(
            symbol=command.symbol,
            timeframe=command.timeframe,
            start_ts_ms=window.start_ts_ms,
            end_ts_ms=window.end_ts_ms,
        )
        return RepairPlan(
            strategy=RepairStrategy.GAP_REPAIR,
            symbol=command.symbol,
            timeframe=command.timeframe,
            window=window,
            tasks=detect_gap_tasks(timestamps=timestamps, timeframe=command.timeframe, window=window),
        )


class RunHistoricalBackfillUseCase(_BaseRepairUseCase):
    async def _build_plan(self, command: RepairCommand) -> RepairPlan:
        window = self._normalized_window(command)
        tasks = detect_gap_tasks(timestamps=[], timeframe=command.timeframe, window=window)
        return BackfillPlan(
            strategy=RepairStrategy.BACKFILL,
            symbol=command.symbol,
            timeframe=command.timeframe,
            window=window,
            tasks=tasks,
        )
