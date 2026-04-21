from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.candles.domain.repair import (
    BackfillPlan,
    NoProgressPolicy,
    RepairExecutionMode,
    RepairPlan,
    RepairStrategy,
    RepairVerificationMethod,
    RepairWindow,
    clamp_window_to_closed_bars,
    classify_repair_outcome,
    detect_gap_tasks,
    sanitize_repair_candle,
    summarize_repair_verification,
    validate_repair_candles,
)
from src.candles.domain.repair_timeframes import window_padding

from .dto import RepairCommand, RepairResult
from .progress import NoProgressTracker

if TYPE_CHECKING:
    from .ports import (
        CandleCoverageQueryPort,
        HistoricalCandleSourcePort,
        RepairCandleStorePort,
        TelemetryPort,
    )


logger = logging.getLogger(__name__)


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
        no_progress_policy: NoProgressPolicy | None = None,
    ) -> None:
        self._coverage_query = coverage_query
        self._historical_source = historical_source
        self._repair_store = repair_store
        self._telemetry = telemetry or _NullTelemetry()
        self._no_progress_policy = no_progress_policy or NoProgressPolicy()
        self._no_progress_trackers: dict[tuple[str, str], NoProgressTracker] = {}

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
                remaining_gap_tasks=plan.gap_tasks,
                remaining_requested_bars=plan.requested_bars,
                verification_method=RepairVerificationMethod.PLAN_ONLY,
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
                remaining_gap_tasks=plan.gap_tasks,
                remaining_requested_bars=plan.requested_bars,
                verification_method=RepairVerificationMethod.PLAN_ONLY,
                watermark_updated=False,
            )

        rows_written = 0
        fetch_calls = 0
        total_received = 0
        remaining_missing_before = await self._coverage_query.count_missing_timestamps(
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            start_ts_ms=plan.window.start_ts_ms,
            end_ts_ms=plan.window.end_ts_ms,
        )

        for task in plan.tasks:
            padding_ms = window_padding(plan.timeframe, command.padding_bars)
            candles = await self._historical_source.fetch_range(
                symbol=plan.symbol,
                timeframe=plan.timeframe,
                start_ts_ms=max(plan.window.start_ts_ms, task.start_ts_ms - padding_ms),
                end_ts_ms=min(plan.window.end_ts_ms, task.end_ts_ms + padding_ms),
            )
            fetch_calls += 1
            valid_rows = validate_repair_candles(
                candles=candles,
                task_window=RepairWindow(task.start_ts_ms, task.end_ts_ms),
                closed_until_ts_ms=plan.window.end_ts_ms,
            )
            validated = self._sanitize_candles(valid_rows)
            total_received += len(validated)
            rows_written += await self._repair_store.selective_upsert_candles(
                symbol=plan.symbol,
                timeframe=plan.timeframe,
                candles=validated,
            )

        remaining_missing_after = await self._coverage_query.count_missing_timestamps(
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            start_ts_ms=plan.window.start_ts_ms,
            end_ts_ms=plan.window.end_ts_ms,
        )

        verified_timestamps = await self._coverage_query.list_timestamps(
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            start_ts_ms=plan.window.start_ts_ms,
            end_ts_ms=plan.window.end_ts_ms,
        )
        verification = summarize_repair_verification(
            timestamps=verified_timestamps,
            timeframe=plan.timeframe,
            window=plan.window,
        )
        verified = verification.remaining_gap_tasks == 0
        progress = remaining_missing_before - remaining_missing_after
        outcome = classify_repair_outcome(
            requested=plan.requested_bars,
            received=total_received,
            exception=False,
        )
        api_fill_ratio = total_received / max(plan.requested_bars, 1)
        write_success_ratio = rows_written / max(total_received, 1)

        tracker = self._get_no_progress_tracker(
            symbol=plan.symbol,
            timeframe=plan.timeframe,
        )
        tracker.record(progress)
        if tracker.should_escalate():
            raise ValueError(
                f"no progress on critical TF {plan.timeframe}: "
                f"{self._no_progress_policy.no_progress_threshold} iterations in a row"
            )

        self._telemetry.event(
            "candles.repair.completed",
            symbol=plan.symbol,
            timeframe=plan.timeframe,
            strategy=plan.strategy.value,
            requested=plan.requested_bars,
            received=total_received,
            written=rows_written,
            rows_written=rows_written,
            fetch_calls=fetch_calls,
            verified=verified,
            verification_method=verification.method.value,
            remaining_gap_tasks=verification.remaining_gap_tasks,
            remaining_requested_bars=verification.remaining_requested_bars,
            remaining_missing_before=remaining_missing_before,
            remaining_missing_after=remaining_missing_after,
            progress=progress,
            api_fill_ratio=api_fill_ratio,
            write_success_ratio=write_success_ratio,
            outcome=outcome.value,
        )
        logger.info(
            "repair.outcome",
            extra={
                "repair_symbol": plan.symbol,
                "repair_timeframe": plan.timeframe,
                "repair_strategy": plan.strategy.value,
                "repair_mode": command.mode.value,
                "repair_outcome": outcome.value,
                "repair_requested_bars": plan.requested_bars,
                "repair_received_bars": total_received,
                "repair_rows_written": rows_written,
                "repair_fetch_calls": fetch_calls,
                "repair_verified": verified,
                "repair_verification_method": verification.method.value,
                "repair_remaining_gap_tasks": verification.remaining_gap_tasks,
                "repair_remaining_requested_bars": verification.remaining_requested_bars,
                "repair_remaining_missing_before": remaining_missing_before,
                "repair_remaining_missing_after": remaining_missing_after,
                "repair_progress": progress,
                "repair_api_fill_ratio": api_fill_ratio,
                "repair_write_success_ratio": write_success_ratio,
            },
        )
        return RepairResult(
            mode=command.mode,
            strategy=command.strategy,
            plan=plan,
            fetch_calls=fetch_calls,
            rows_written=rows_written,
            verified=verified,
            remaining_gap_tasks=verification.remaining_gap_tasks,
            remaining_requested_bars=verification.remaining_requested_bars,
            verification_method=verification.method,
            watermark_updated=False,
        )

    def _get_no_progress_tracker(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> NoProgressTracker:
        key = (symbol, timeframe)
        if key not in self._no_progress_trackers:
            self._no_progress_trackers[key] = NoProgressTracker(
                policy=self._no_progress_policy,
                timeframe=timeframe,
            )
        return self._no_progress_trackers[key]

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
