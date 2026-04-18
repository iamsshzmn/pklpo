from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.candles.domain.repair import RepairWindow
from src.candles.domain.repair_timeframes import expected_next_open, floor_to_timeframe

if TYPE_CHECKING:
    from .ports import CandleCoverageQueryPort, RepairAnchorMetadataPort

_DAY_MS = 86_400_000


@dataclass(frozen=True)
class AutoApplyWindowPlan:
    start_ts_ms: int
    end_ts_ms: int
    closed_until_ts_ms: int


def _ceil_to_timeframe(timestamp_ms: int, timeframe: str) -> int:
    floored_ts_ms = floor_to_timeframe(timestamp_ms, timeframe)
    if floored_ts_ms == timestamp_ms:
        return floored_ts_ms
    return expected_next_open(floored_ts_ms, timeframe)


def resolve_repair_window(
    *,
    start_ts_ms: int | None,
    end_ts_ms: int | None,
    window_hours: int,
    now_ts_ms: int,
) -> RepairWindow:
    has_start = start_ts_ms is not None
    has_end = end_ts_ms is not None
    if has_start != has_end:
        raise ValueError("swap_repair requires both start and end when either is provided")

    if has_start and has_end:
        resolved_start_ts_ms = int(start_ts_ms)
        resolved_end_ts_ms = min(int(end_ts_ms), now_ts_ms)
    else:
        resolved_end_ts_ms = now_ts_ms - (now_ts_ms % 60_000)
        resolved_start_ts_ms = resolved_end_ts_ms - (window_hours * 3_600_000)

    if resolved_start_ts_ms >= resolved_end_ts_ms:
        raise ValueError("swap_repair window must satisfy start < end")
    return RepairWindow(
        start_ts_ms=resolved_start_ts_ms,
        end_ts_ms=resolved_end_ts_ms,
    )


async def plan_auto_apply_window(
    *,
    coverage_query: CandleCoverageQueryPort,
    symbol: str,
    timeframe: str,
    max_range_days: int,
    now_ts_ms: int,
    anchor_ts_ms: int | None = None,
    anchor_strategy: str = "first-coverage",
    anchor_metadata: RepairAnchorMetadataPort | None = None,
) -> AutoApplyWindowPlan:
    closed_until_ts_ms = floor_to_timeframe(now_ts_ms, timeframe)
    min_ts_ms, _ = await coverage_query.get_coverage_bounds(
        symbol=symbol,
        timeframe=timeframe,
        end_ts_ms=closed_until_ts_ms,
    )
    if min_ts_ms is None:
        resolved_anchor_ts_ms = anchor_ts_ms
        if resolved_anchor_ts_ms is None and anchor_strategy == "listing-date":
            if anchor_metadata is None:
                raise ValueError(
                    "swap_repair auto-apply listing-date anchor requires anchor metadata"
                )
            listing_anchor_metadata = await anchor_metadata.get_listing_anchor_metadata(
                symbol=symbol
            )
            if (
                listing_anchor_metadata is None
                or listing_anchor_metadata.metadata_refreshed_at_ms is None
            ):
                raise ValueError(
                    f"swap_repair auto-apply listing-date anchor metadata lookup returned null freshness timestamp for symbol {symbol}"
                )
            resolved_anchor_ts_ms = listing_anchor_metadata.list_time_ts_ms
            if resolved_anchor_ts_ms is None:
                raise ValueError(
                    f"swap_repair auto-apply listing-date anchor metadata lookup returned null listing time for symbol {symbol}"
                )

        if resolved_anchor_ts_ms is None:
            raise ValueError(
                "swap_repair auto-apply requires existing coverage, anchor_ts_ms, or listing-date metadata"
            )

        anchor_start_ts_ms = _ceil_to_timeframe(resolved_anchor_ts_ms, timeframe)
        if anchor_start_ts_ms > closed_until_ts_ms:
            raise ValueError(
                "swap_repair auto-apply anchor must be at or before the closed window"
            )

        max_range_ms = max_range_days * _DAY_MS
        return AutoApplyWindowPlan(
            start_ts_ms=anchor_start_ts_ms,
            end_ts_ms=min(closed_until_ts_ms, anchor_start_ts_ms + max_range_ms),
            closed_until_ts_ms=closed_until_ts_ms,
        )

    first_gap_start_ts_ms = await coverage_query.find_first_gap_start_ts_ms(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=min_ts_ms,
        end_ts_ms=closed_until_ts_ms,
    )
    if first_gap_start_ts_ms is None:
        return AutoApplyWindowPlan(
            start_ts_ms=closed_until_ts_ms,
            end_ts_ms=closed_until_ts_ms,
            closed_until_ts_ms=closed_until_ts_ms,
        )

    max_range_ms = max_range_days * _DAY_MS
    window_end_ts_ms = min(closed_until_ts_ms, first_gap_start_ts_ms + max_range_ms)
    return AutoApplyWindowPlan(
        start_ts_ms=first_gap_start_ts_ms,
        end_ts_ms=window_end_ts_ms,
        closed_until_ts_ms=closed_until_ts_ms,
    )
