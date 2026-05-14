from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.candles.domain.okx_calendar import OKXCandleCalendar


def compute_target_window(
    *,
    now_ms: int,
    lookback_days: int,
    listing_time_ms: int | None,
    timeframe: str,
    calendar: OKXCandleCalendar,
) -> tuple[int, int]:
    """Return (target_start_ts, target_end_ts) aligned to closed bar boundaries.

    target_start_ts = floor_open(max(now_ms - lookback_days*day_ms, listing_time_ms or 0))
    target_end_ts   = floor_open(now_ms)
    """
    day_ms = 86_400_000
    lookback_start = now_ms - lookback_days * day_ms
    if listing_time_ms is not None:
        lookback_start = max(lookback_start, listing_time_ms)
    target_start_ts = calendar.floor_open(lookback_start, timeframe)
    target_end_ts = calendar.floor_open(now_ms, timeframe)
    return target_start_ts, target_end_ts


def compute_chunk_window(
    *,
    checkpoint_ts: int,
    chunk_bars: int,
    timeframe_ms: int,
) -> tuple[int, int]:
    """Return (chunk_start_ts, chunk_end_ts) for one backward page fetch.

    chunk_end_ts   = checkpoint_ts
    chunk_start_ts = checkpoint_ts - chunk_bars * timeframe_ms
    """
    chunk_start_ts = checkpoint_ts - chunk_bars * timeframe_ms
    return chunk_start_ts, checkpoint_ts
