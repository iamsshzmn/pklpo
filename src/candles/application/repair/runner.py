from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from src.candles.domain.repair import (
    BackfillPlan,
    RepairPlan,
    RepairWindow,
    detect_gap_tasks,
)

from .dto import RepairPreview
from .planning import plan_auto_apply_window, resolve_repair_window
from .summary import (
    RepairSummary,
    build_noop_repair_summary,
    merge_repair_summaries,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from src.candles.domain.repair import (
        RepairExecutionMode,
        RepairGuardrails,
        RepairStrategy,
    )

    from .ports import CandleCoverageQueryPort, RepairAnchorMetadataPort


class RepairWindowExecutor(Protocol):
    async def __call__(self, *, start_ts_ms: int, end_ts_ms: int) -> RepairSummary: ...


@dataclass(frozen=True)
class RepairTimeframeRequest:
    symbol: str
    timeframe: str
    mode: RepairExecutionMode
    strategy: RepairStrategy
    start_ts_ms: int | None
    end_ts_ms: int | None
    window_hours: int
    max_range_days: int
    padding_bars: int
    auto_apply_window: bool
    auto_apply_iteration_limit: int = 100


async def preview_repair_timeframe(
    *,
    symbol: str,
    timeframe: str,
    mode: RepairExecutionMode,
    strategy: RepairStrategy,
    start_ts_ms: int | None,
    end_ts_ms: int | None,
    window_hours: int,
    max_range_days: int,
    now_ts_ms: int,
    auto_apply_window: bool,
    coverage_query: CandleCoverageQueryPort,
    guardrails: RepairGuardrails,
    anchor_ts_ms: int | None = None,
    anchor_strategy: str = "first-coverage",
    anchor_metadata: RepairAnchorMetadataPort | None = None,
) -> RepairPreview:
    closed_until_ts_ms = now_ts_ms
    if auto_apply_window:
        auto_apply_plan = await plan_auto_apply_window(
            coverage_query=coverage_query,
            symbol=symbol,
            timeframe=timeframe,
            max_range_days=max_range_days,
            now_ts_ms=now_ts_ms,
            anchor_ts_ms=anchor_ts_ms,
            anchor_strategy=anchor_strategy,
            anchor_metadata=anchor_metadata,
        )
        closed_until_ts_ms = auto_apply_plan.closed_until_ts_ms
        if auto_apply_plan.start_ts_ms == auto_apply_plan.end_ts_ms:
            preview_window = RepairWindow(
                start_ts_ms=closed_until_ts_ms,
                end_ts_ms=closed_until_ts_ms,
            )
        else:
            preview_window = RepairWindow(
                start_ts_ms=auto_apply_plan.start_ts_ms,
                end_ts_ms=closed_until_ts_ms,
            )
    else:
        preview_window = resolve_repair_window(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            window_hours=window_hours,
            now_ts_ms=now_ts_ms,
        )

    timestamps = await coverage_query.list_timestamps(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=preview_window.start_ts_ms,
        end_ts_ms=preview_window.end_ts_ms,
    )
    tasks = detect_gap_tasks(
        timestamps=timestamps,
        timeframe=timeframe,
        window=preview_window,
    )
    plan_cls = BackfillPlan if strategy.value == "backfill" else RepairPlan
    plan = plan_cls(
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        window=preview_window,
        tasks=tasks,
    )
    guardrail_violations = tuple(
        violation.code for violation in guardrails.check(plan)
    )
    if guardrail_violations:
        _guardrail_risk = "high"
    elif guardrails.max_requested_bars_per_run > 0:
        ratio = plan.requested_bars / guardrails.max_requested_bars_per_run
        if ratio >= 0.9:
            _guardrail_risk = "high"
        elif ratio >= 0.5:
            _guardrail_risk = "medium"
        else:
            _guardrail_risk = "ok"
    else:
        _guardrail_risk = "ok"

    if plan.requested_bars <= 0:
        expected_iteration_count = 0
    elif auto_apply_window:
        max_range_ms = max_range_days * 86_400_000
        expected_iteration_count = max(
            1,
            math.ceil(
                (preview_window.end_ts_ms - preview_window.start_ts_ms) / max_range_ms
            ),
        )
    else:
        expected_iteration_count = 1

    return RepairPreview(
        requested_mode=mode,
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe,
        window=preview_window,
        auto_apply_window=auto_apply_window,
        gap_tasks=plan.gap_tasks,
        requested_bars=plan.requested_bars,
        expected_iteration_count=expected_iteration_count,
        guardrail_risk=_guardrail_risk,
        guardrail_violations=guardrail_violations,
    )


async def run_repair_timeframe(
    *,
    validated: Mapping[str, Any],
    timeframe: str,
    start_ts_ms: int | None,
    end_ts_ms: int | None,
    window_hours: int,
    max_range_days: int,
    now_ts_ms: int,
    auto_apply_window: bool,
    coverage_query: CandleCoverageQueryPort,
    execute_once: RepairWindowExecutor,
    auto_apply_iteration_limit: int = 100,
    anchor_ts_ms: int | None = None,
    anchor_strategy: str = "first-coverage",
    anchor_metadata: RepairAnchorMetadataPort | None = None,
) -> RepairSummary:
    if not auto_apply_window:
        window = resolve_repair_window(
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            window_hours=window_hours,
            now_ts_ms=now_ts_ms,
        )
        return await execute_once(
            start_ts_ms=window.start_ts_ms,
            end_ts_ms=window.end_ts_ms,
        )

    summaries: list[RepairSummary] = []
    closed_until_ts_ms = now_ts_ms

    if auto_apply_iteration_limit < 1:
        raise ValueError("swap_repair auto-apply iteration limit must be >= 1")

    for _ in range(auto_apply_iteration_limit):
        plan = await plan_auto_apply_window(
            coverage_query=coverage_query,
            symbol=str(validated.get("symbol", "")),
            timeframe=timeframe,
            max_range_days=max_range_days,
            now_ts_ms=now_ts_ms,
            anchor_ts_ms=anchor_ts_ms,
            anchor_strategy=anchor_strategy,
            anchor_metadata=anchor_metadata,
        )
        closed_until_ts_ms = plan.closed_until_ts_ms
        if plan.start_ts_ms == plan.end_ts_ms:
            break

        summary = await execute_once(
            start_ts_ms=plan.start_ts_ms,
            end_ts_ms=plan.end_ts_ms,
        )
        summaries.append(summary)
        if summary.remaining_gap_tasks <= 0:
            break

    if not summaries:
        return build_noop_repair_summary(
            validated=validated,
            timeframe=timeframe,
            closed_until_ts_ms=closed_until_ts_ms,
        )

    return merge_repair_summaries(
        validated=validated,
        timeframe=timeframe,
        summaries=summaries,
        closed_until_ts_ms=closed_until_ts_ms,
    )
