from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.candles.domain.repair import RepairWindow, detect_gap_tasks
from src.candles.domain.repair_timeframes import expected_next_open, floor_to_timeframe

if TYPE_CHECKING:
    from .ports import CandleCoverageQueryPort, RepairAnchorMetadataPort

_DAY_MS = 86_400_000

TIMEFRAME_BARS_PER_DAY: dict[str, float] = {
    "1m": 1440.0,
    "1H": 24.0,
    "4H": 6.0,
    "1D": 1.0,
    "1W": 1.0 / 7,
    "1M": 1.0 / 30,
}


def min_bars_for_window(start_ts_ms: int, end_ts_ms: int, timeframe: str) -> int:
    """Return the minimum expected bars for a window, with 5% padding."""
    bars_per_day = TIMEFRAME_BARS_PER_DAY.get(timeframe, 1.0)
    span_days = (end_ts_ms - start_ts_ms) / _DAY_MS
    return max(1, int(span_days * bars_per_day * 1.05))


@dataclass(frozen=True)
class AutoApplyWindowPlan:
    start_ts_ms: int
    end_ts_ms: int
    closed_until_ts_ms: int


@dataclass(frozen=True)
class RepairChunk:
    start_ts_ms: int
    end_ts_ms: int
    requested_bars: int


@dataclass(frozen=True)
class RepairGap:
    start_ts_ms: int
    end_ts_ms: int
    missing_bars: int
    chunks: tuple[RepairChunk, ...]


@dataclass(frozen=True)
class TailFirstRepairPlan:
    start_ts_ms: int
    end_ts_ms: int
    closed_until_ts_ms: int
    gaps: tuple[RepairGap, ...]


def _ceil_to_timeframe(timestamp_ms: int, timeframe: str) -> int:
    floored_ts_ms = floor_to_timeframe(timestamp_ms, timeframe)
    if floored_ts_ms == timestamp_ms:
        return floored_ts_ms
    return expected_next_open(floored_ts_ms, timeframe)


async def _resolve_anchor_start_ts_ms(
    *,
    symbol: str,
    timeframe: str,
    closed_until_ts_ms: int,
    anchor_ts_ms: int | None,
    anchor_strategy: str,
    anchor_metadata: RepairAnchorMetadataPort | None,
) -> int | None:
    resolved_anchor_ts_ms = anchor_ts_ms
    if resolved_anchor_ts_ms is None and anchor_strategy == "listing-date":
        if anchor_metadata is None:
            raise ValueError("swap_repair auto-apply listing-date anchor requires anchor metadata")
        listing_anchor_metadata = await anchor_metadata.get_listing_anchor_metadata(symbol=symbol)
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
        return None

    anchor_start_ts_ms = _ceil_to_timeframe(resolved_anchor_ts_ms, timeframe)
    if anchor_start_ts_ms > closed_until_ts_ms:
        raise ValueError("swap_repair auto-apply anchor must be at or before the closed window")
    return anchor_start_ts_ms


def _trailing_window_start_ts_ms(
    *,
    floor_ts_ms: int,
    closed_until_ts_ms: int,
    max_range_days: int,
) -> int:
    max_range_ms = max_range_days * _DAY_MS
    return max(floor_ts_ms, closed_until_ts_ms - max_range_ms)


def _split_gap_into_desc_chunks(
    *,
    start_ts_ms: int,
    end_ts_ms: int,
    timeframe: str,
    chunk_size_bars: int,
) -> tuple[RepairChunk, ...]:
    if chunk_size_bars < 1:
        raise ValueError("swap_repair tail-first chunk_size_bars must be >= 1")

    bar_starts: list[int] = []
    cursor = start_ts_ms
    while cursor < end_ts_ms:
        bar_starts.append(cursor)
        cursor = expected_next_open(cursor, timeframe)

    chunks: list[RepairChunk] = []
    total_bars = len(bar_starts)
    for chunk_end_index in range(total_bars, 0, -chunk_size_bars):
        chunk_start_index = max(0, chunk_end_index - chunk_size_bars)
        chunk_bar_starts = bar_starts[chunk_start_index:chunk_end_index]
        chunk_end_ts_ms = (
            end_ts_ms
            if chunk_end_index == total_bars
            else bar_starts[chunk_end_index]
        )
        chunks.append(
            RepairChunk(
                start_ts_ms=chunk_bar_starts[0],
                end_ts_ms=chunk_end_ts_ms,
                requested_bars=len(chunk_bar_starts),
            )
        )
    return tuple(chunks)


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
    anchor_start_ts_ms = await _resolve_anchor_start_ts_ms(
        symbol=symbol,
        timeframe=timeframe,
        closed_until_ts_ms=closed_until_ts_ms,
        anchor_ts_ms=anchor_ts_ms,
        anchor_strategy=anchor_strategy,
        anchor_metadata=anchor_metadata,
    )
    min_ts_ms, _ = await coverage_query.get_coverage_bounds(
        symbol=symbol,
        timeframe=timeframe,
        end_ts_ms=closed_until_ts_ms,
    )
    if min_ts_ms is None:
        if anchor_start_ts_ms is None:
            raise ValueError(
                "swap_repair auto-apply requires existing coverage, anchor_ts_ms, or listing-date metadata"
            )

        max_range_ms = max_range_days * _DAY_MS
        return AutoApplyWindowPlan(
            start_ts_ms=anchor_start_ts_ms,
            end_ts_ms=min(closed_until_ts_ms, anchor_start_ts_ms + max_range_ms),
            closed_until_ts_ms=closed_until_ts_ms,
        )

    if anchor_start_ts_ms is not None and anchor_start_ts_ms < min_ts_ms:
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


async def plan_tail_first_repair(
    *,
    coverage_query: CandleCoverageQueryPort,
    symbol: str,
    timeframe: str,
    max_range_days: int,
    now_ts_ms: int,
    chunk_size_bars: int,
    anchor_ts_ms: int | None = None,
    anchor_strategy: str = "first-coverage",
    anchor_metadata: RepairAnchorMetadataPort | None = None,
) -> TailFirstRepairPlan:
    closed_until_ts_ms = floor_to_timeframe(now_ts_ms, timeframe)
    anchor_start_ts_ms = await _resolve_anchor_start_ts_ms(
        symbol=symbol,
        timeframe=timeframe,
        closed_until_ts_ms=closed_until_ts_ms,
        anchor_ts_ms=anchor_ts_ms,
        anchor_strategy=anchor_strategy,
        anchor_metadata=anchor_metadata,
    )
    min_ts_ms, _ = await coverage_query.get_coverage_bounds(
        symbol=symbol,
        timeframe=timeframe,
        end_ts_ms=closed_until_ts_ms,
    )

    if min_ts_ms is None and anchor_start_ts_ms is None:
        raise ValueError(
            "swap_repair auto-apply requires existing coverage, anchor_ts_ms, or listing-date metadata"
        )

    planning_floor_ts_ms = (
        anchor_start_ts_ms
        if min_ts_ms is None
        else (
            min_ts_ms
            if anchor_start_ts_ms is None
            else min(anchor_start_ts_ms, min_ts_ms)
        )
    )
    start_ts_ms = _trailing_window_start_ts_ms(
        floor_ts_ms=planning_floor_ts_ms,
        closed_until_ts_ms=closed_until_ts_ms,
        max_range_days=max_range_days,
    )
    planning_window = RepairWindow(
        start_ts_ms=start_ts_ms,
        end_ts_ms=closed_until_ts_ms,
    )
    timestamps = await coverage_query.list_timestamps(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=planning_window.start_ts_ms,
        end_ts_ms=planning_window.end_ts_ms,
    )
    detected_gaps = detect_gap_tasks(
        timestamps=timestamps,
        timeframe=timeframe,
        window=planning_window,
    )
    gaps = tuple(
        RepairGap(
            start_ts_ms=gap.start_ts_ms,
            end_ts_ms=gap.end_ts_ms,
            missing_bars=gap.missing_bars,
            chunks=_split_gap_into_desc_chunks(
                start_ts_ms=gap.start_ts_ms,
                end_ts_ms=gap.end_ts_ms,
                timeframe=timeframe,
                chunk_size_bars=chunk_size_bars,
            ),
        )
        for gap in reversed(detected_gaps)
    )
    return TailFirstRepairPlan(
        start_ts_ms=planning_window.start_ts_ms,
        end_ts_ms=planning_window.end_ts_ms,
        closed_until_ts_ms=closed_until_ts_ms,
        gaps=gaps,
    )
