from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.candles.application.repair import (
    RepairCommand,
    RepairPreview,
    RepairSummary,
    RunGapRepairUseCase,
    RunHistoricalBackfillUseCase,
    preview_repair_timeframe,
    run_repair_timeframe,
)
from src.candles.domain.repair import (
    NoProgressPolicy,
    RepairExecutionMode,
    RepairGuardrails,
    RepairStrategy,
)
from src.candles.infrastructure.adapters import build_market_data_adapter
from src.candles.infrastructure.repair_repository import RepairCandlesRepository
from src.candles.interfaces.swap_sync import (
    _MarketDataPortAdapter,
    _TracingTelemetryAdapter,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable


@dataclass(slots=True)
class _RepairRuntime:
    repository: RepairCandlesRepository
    telemetry: _TracingTelemetryAdapter
    use_case: RunGapRepairUseCase | RunHistoricalBackfillUseCase


class _HistoricalRangeSourceAdapter:
    """Historical range fetch adapter for repair/backfill use cases.

    Delegates to the market data port's dedicated ``fetch_history_candles``
    entry point. The previous implementation here paginated by a ``before``
    cursor through the fast-path ``fetch_candles`` method and produced zero
    rows for most real OKX tasks — see the root-cause NOTE on
    ``CcxtOKXAdapter.get_history_candles``.
    """

    def __init__(self, market_data: _MarketDataPortAdapter) -> None:
        self._market_data = market_data

    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        if start_ts_ms >= end_ts_ms:
            return []
        return await self._market_data.fetch_history_candles(
            instrument_id=symbol,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )


class _NoopHistoricalRangeSource:
    async def fetch_range(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> list[dict[str, Any]]:
        return []


def _build_guardrails(
    *,
    max_gap_tasks_per_run: int,
    max_requested_bars_per_run: int,
    max_range_days: int,
    max_fail_ratio: float,
) -> RepairGuardrails:
    return RepairGuardrails(
        max_gap_tasks_per_run=max_gap_tasks_per_run,
        max_requested_bars_per_run=max_requested_bars_per_run,
        max_range_days=max_range_days,
        max_fail_ratio=max_fail_ratio,
    )


def _build_repair_command(
    *,
    symbol: str,
    timeframe: str,
    start_ts_ms: int,
    end_ts_ms: int,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    guardrails: RepairGuardrails,
    now_ts_ms: int,
    padding_bars: int,
) -> RepairCommand:
    return RepairCommand(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        mode=mode,
        strategy=strategy,
        guardrails=guardrails,
        now_ts_ms=now_ts_ms,
        padding_bars=padding_bars,
    )


def _build_repair_use_case(
    *,
    repository: RepairCandlesRepository,
    telemetry: _TracingTelemetryAdapter,
    strategy: RepairStrategy,
    source: Any,
    no_progress_policy: NoProgressPolicy | None = None,
) -> RunGapRepairUseCase | RunHistoricalBackfillUseCase:
    use_case_cls = (
        RunHistoricalBackfillUseCase
        if strategy is RepairStrategy.BACKFILL
        else RunGapRepairUseCase
    )
    return use_case_cls(
        coverage_query=repository,
        historical_source=source,
        repair_store=repository,
        telemetry=telemetry,
        no_progress_policy=no_progress_policy,
    )


def _build_no_progress_policy(
    *,
    critical_timeframes: list[str] | tuple[str, ...] | None,
    no_progress_threshold: int | None,
) -> NoProgressPolicy | None:
    if critical_timeframes is None and no_progress_threshold is None:
        return None
    kwargs: dict[str, Any] = {}
    if critical_timeframes is not None:
        kwargs["critical_timeframes"] = frozenset(str(tf) for tf in critical_timeframes)
    if no_progress_threshold is not None:
        kwargs["no_progress_threshold"] = int(no_progress_threshold)
    return NoProgressPolicy(**kwargs)


@asynccontextmanager
async def _open_repair_runtime(
    *,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    config: dict[str, Any] | None,
    no_progress_policy: NoProgressPolicy | None = None,
) -> AsyncIterator[_RepairRuntime]:
    repository = RepairCandlesRepository()
    telemetry = _TracingTelemetryAdapter()

    if mode is RepairExecutionMode.APPLY:
        market_adapter = build_market_data_adapter(config or {})
        async with _MarketDataPortAdapter(market_adapter) as market_data:
            source = _HistoricalRangeSourceAdapter(market_data)
            yield _RepairRuntime(
                repository=repository,
                telemetry=telemetry,
                use_case=_build_repair_use_case(
                    repository=repository,
                    telemetry=telemetry,
                    strategy=strategy,
                    source=source,
                    no_progress_policy=no_progress_policy,
                ),
            )
        return

    yield _RepairRuntime(
        repository=repository,
        telemetry=telemetry,
        use_case=_build_repair_use_case(
            repository=repository,
            telemetry=telemetry,
            strategy=strategy,
            source=_NoopHistoricalRangeSource(),
            no_progress_policy=no_progress_policy,
        ),
    )


async def _run_repair_window_summary(
    *,
    use_case: Any,
    command: RepairCommand,
    padding_bars: int,
) -> RepairSummary:
    result = await use_case.run(command)
    violations = command.guardrails.check(result.plan)
    return RepairSummary.from_result(
        result,
        padding_bars=padding_bars,
        guardrail_violations=[violation.code for violation in violations],
    )


def _build_execute_once(
    *,
    use_case: RunGapRepairUseCase | RunHistoricalBackfillUseCase,
    symbol: str,
    timeframe: str,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    guardrails: RepairGuardrails,
    now_ts_ms: int,
    padding_bars: int,
) -> Callable[..., Awaitable[RepairSummary]]:
    async def _execute_once(
        *,
        start_ts_ms: int,
        end_ts_ms: int,
    ) -> RepairSummary:
        command = _build_repair_command(
            symbol=symbol,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            mode=mode,
            strategy=strategy,
            guardrails=guardrails,
            now_ts_ms=now_ts_ms,
            padding_bars=padding_bars,
        )
        return await _run_repair_window_summary(
            use_case=use_case,
            command=command,
            padding_bars=padding_bars,
        )

    return _execute_once


async def _run_swap_repair_once_summary(
    *,
    symbol: str,
    timeframe: str,
    start_ts_ms: int,
    end_ts_ms: int,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    max_gap_tasks_per_run: int,
    max_requested_bars_per_run: int,
    max_range_days: int,
    max_fail_ratio: float,
    padding_bars: int,
    config: dict[str, Any] | None = None,
    critical_timeframes: list[str] | tuple[str, ...] | None = None,
    no_progress_threshold: int | None = None,
) -> RepairSummary:
    now_ts_ms = int(datetime.now(UTC).timestamp() * 1000)
    guardrails = _build_guardrails(
        max_gap_tasks_per_run=max_gap_tasks_per_run,
        max_requested_bars_per_run=max_requested_bars_per_run,
        max_range_days=max_range_days,
        max_fail_ratio=max_fail_ratio,
    )
    no_progress_policy = _build_no_progress_policy(
        critical_timeframes=critical_timeframes,
        no_progress_threshold=no_progress_threshold,
    )
    async with _open_repair_runtime(
        mode=mode,
        strategy=strategy,
        config=config,
        no_progress_policy=no_progress_policy,
    ) as runtime:
        execute_once = _build_execute_once(
            use_case=runtime.use_case,
            symbol=symbol,
            timeframe=timeframe,
            mode=mode,
            strategy=strategy,
            guardrails=guardrails,
            now_ts_ms=now_ts_ms,
            padding_bars=padding_bars,
        )
        return await execute_once(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
        )


async def run_swap_repair(
    *,
    symbol: str,
    timeframe: str,
    start_ts_ms: int,
    end_ts_ms: int,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    max_gap_tasks_per_run: int,
    max_requested_bars_per_run: int,
    max_range_days: int,
    max_fail_ratio: float,
    padding_bars: int,
    config: dict[str, Any] | None = None,
    critical_timeframes: list[str] | tuple[str, ...] | None = None,
    no_progress_threshold: int | None = None,
) -> dict[str, Any]:
    summary = await _run_swap_repair_once_summary(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        mode=mode,
        strategy=strategy,
        max_gap_tasks_per_run=max_gap_tasks_per_run,
        max_requested_bars_per_run=max_requested_bars_per_run,
        max_range_days=max_range_days,
        max_fail_ratio=max_fail_ratio,
        padding_bars=padding_bars,
        config=config,
        critical_timeframes=critical_timeframes,
        no_progress_threshold=no_progress_threshold,
    )
    return summary.to_dict()


async def plan_swap_repair(
    *,
    symbol: str,
    timeframe: str,
    start_ts_ms: int | None,
    end_ts_ms: int | None,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    auto_apply_window: bool,
    max_gap_tasks_per_run: int,
    max_requested_bars_per_run: int,
    max_range_days: int,
    max_fail_ratio: float,
    padding_bars: int,
    window_hours: int = 6,
    anchor_ts_ms: int | None = None,
    auto_apply_anchor_strategy: str = "first-coverage",
) -> dict[str, Any]:
    del max_fail_ratio, padding_bars

    repository = RepairCandlesRepository()
    now_ts_ms = int(datetime.now(UTC).timestamp() * 1000)
    preview: RepairPreview = await preview_repair_timeframe(
        symbol=symbol,
        timeframe=timeframe,
        mode=mode,
        strategy=strategy,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        window_hours=window_hours,
        max_range_days=max_range_days,
        now_ts_ms=now_ts_ms,
        auto_apply_window=auto_apply_window,
        coverage_query=repository,
        guardrails=_build_guardrails(
            max_gap_tasks_per_run=max_gap_tasks_per_run,
            max_requested_bars_per_run=max_requested_bars_per_run,
            max_range_days=max_range_days,
            max_fail_ratio=0.0,
        ),
        anchor_ts_ms=anchor_ts_ms,
        anchor_strategy=auto_apply_anchor_strategy,
        anchor_metadata=repository,
    )
    return preview.to_dict()


async def run_swap_repair_timeframe(
    *,
    symbol: str,
    timeframe: str,
    start_ts_ms: int | None,
    end_ts_ms: int | None,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    auto_apply_window: bool,
    max_gap_tasks_per_run: int,
    max_requested_bars_per_run: int,
    max_range_days: int,
    max_fail_ratio: float,
    padding_bars: int,
    window_hours: int = 6,
    config: dict[str, Any] | None = None,
    auto_apply_iteration_limit: int = 100,
    anchor_ts_ms: int | None = None,
    auto_apply_anchor_strategy: str = "first-coverage",
    critical_timeframes: list[str] | tuple[str, ...] | None = None,
    no_progress_threshold: int | None = None,
) -> dict[str, Any]:
    if auto_apply_window and mode is not RepairExecutionMode.APPLY:
        raise ValueError("swap_repair auto-apply requires apply mode")
    now_ts_ms = int(datetime.now(UTC).timestamp() * 1000)
    guardrails = _build_guardrails(
        max_gap_tasks_per_run=max_gap_tasks_per_run,
        max_requested_bars_per_run=max_requested_bars_per_run,
        max_range_days=max_range_days,
        max_fail_ratio=max_fail_ratio,
    )
    no_progress_policy = _build_no_progress_policy(
        critical_timeframes=critical_timeframes,
        no_progress_threshold=no_progress_threshold,
    )
    validated = {
        "symbol": symbol,
        "repair_strategy": strategy.value,
        "padding_bars": padding_bars,
        "anchor_ts_ms": anchor_ts_ms,
        "auto_apply_anchor_strategy": auto_apply_anchor_strategy,
    }
    async with _open_repair_runtime(
        mode=mode,
        strategy=strategy,
        config=config,
        no_progress_policy=no_progress_policy,
    ) as runtime:
        summary = await run_repair_timeframe(
            validated=validated,
            timeframe=timeframe,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            window_hours=window_hours,
            max_range_days=max_range_days,
            now_ts_ms=now_ts_ms,
            auto_apply_window=auto_apply_window,
            coverage_query=runtime.repository,
            execute_once=_build_execute_once(
                use_case=runtime.use_case,
                symbol=symbol,
                timeframe=timeframe,
                mode=mode,
                strategy=strategy,
                guardrails=guardrails,
                now_ts_ms=now_ts_ms,
                padding_bars=padding_bars,
            ),
            auto_apply_iteration_limit=auto_apply_iteration_limit,
            anchor_ts_ms=anchor_ts_ms,
            anchor_strategy=auto_apply_anchor_strategy,
            anchor_metadata=runtime.repository,
        )
        return summary.to_dict()


async def run_swap_repair_auto_apply(
    *,
    symbol: str,
    timeframe: str,
    strategy: RepairStrategy,
    max_gap_tasks_per_run: int,
    max_requested_bars_per_run: int,
    max_range_days: int,
    max_fail_ratio: float,
    padding_bars: int,
    auto_apply_max_iterations: int = 100,
    config: dict[str, Any] | None = None,
    anchor_ts_ms: int | None = None,
    auto_apply_anchor_strategy: str = "first-coverage",
    critical_timeframes: list[str] | tuple[str, ...] | None = None,
    no_progress_threshold: int | None = None,
) -> dict[str, Any]:
    return await run_swap_repair_timeframe(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=None,
        end_ts_ms=None,
        mode=RepairExecutionMode.APPLY,
        strategy=strategy,
        auto_apply_window=True,
        max_gap_tasks_per_run=max_gap_tasks_per_run,
        max_requested_bars_per_run=max_requested_bars_per_run,
        max_range_days=max_range_days,
        max_fail_ratio=max_fail_ratio,
        padding_bars=padding_bars,
        window_hours=6,
        config=config,
        auto_apply_iteration_limit=auto_apply_max_iterations,
        anchor_ts_ms=anchor_ts_ms,
        auto_apply_anchor_strategy=auto_apply_anchor_strategy,
        critical_timeframes=critical_timeframes,
        no_progress_threshold=no_progress_threshold,
    )
