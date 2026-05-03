from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .timeframes import TF_TO_MS

if TYPE_CHECKING:
    from .repair import GapRange


def is_fixed_step_timeframe(timeframe: str) -> bool:
    return timeframe in TF_TO_MS and timeframe != "1M"


def expected_next_open(timestamp_ms: int, timeframe: str) -> int:
    if is_fixed_step_timeframe(timeframe):
        return timestamp_ms + TF_TO_MS[timeframe]
    if timeframe != "1M":
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    return int(datetime(year, month, 1, tzinfo=UTC).timestamp() * 1000)


def floor_to_timeframe(timestamp_ms: int, timeframe: str) -> int:
    if is_fixed_step_timeframe(timeframe):
        step = TF_TO_MS[timeframe]
        return timestamp_ms - (timestamp_ms % step)
    if timeframe != "1M":
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    return int(datetime(dt.year, dt.month, 1, tzinfo=UTC).timestamp() * 1000)


def floor_to_timeframe_business(timestamp_ms: int, timeframe: str, week_anchor_ts_ms: int) -> int:
    if timeframe != "1W":
        return floor_to_timeframe(timestamp_ms, timeframe)
    step = TF_TO_MS["1W"]
    offset = timestamp_ms - week_anchor_ts_ms
    return week_anchor_ts_ms + ((offset // step) * step)


def _previous_open(timestamp_ms: int, timeframe: str) -> int:
    if timeframe == "1M":
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        year = dt.year - (1 if dt.month == 1 else 0)
        month = 12 if dt.month == 1 else dt.month - 1
        return int(datetime(year, month, 1, tzinfo=UTC).timestamp() * 1000)
    step = TF_TO_MS[timeframe]
    return timestamp_ms - step


def build_last_n_closed_window(
    now_ts_ms: int,
    timeframe: str,
    bars: int,
    week_anchor_ts_ms: int,
) -> tuple[int, int]:
    if bars < 1:
        raise ValueError("bars must be >= 1")
    closed_until_ts_ms = floor_to_timeframe_business(now_ts_ms, timeframe, week_anchor_ts_ms)
    window_start_ts_ms = closed_until_ts_ms
    for _ in range(bars):
        window_start_ts_ms = _previous_open(window_start_ts_ms, timeframe)
    return window_start_ts_ms, closed_until_ts_ms


def list_expected_timestamps(window_start: int, window_end: int, timeframe: str) -> list[int]:
    timestamps: list[int] = []
    cursor = window_start
    while cursor < window_end:
        timestamps.append(cursor)
        cursor = expected_next_open(cursor, timeframe)
    return timestamps


def merge_adjacent_timestamps(
    missing: list[int],
    timeframe: str,
    week_anchor_ts_ms: int,
) -> list[GapRange]:
    from .repair import GapRange

    if not missing:
        return []
    sorted_missing = sorted(
        {
            floor_to_timeframe_business(ts, timeframe, week_anchor_ts_ms)
            for ts in missing
        }
    )
    ranges: list[GapRange] = []
    start_ts_ms = sorted_missing[0]
    prev_ts_ms = sorted_missing[0]
    for timestamp_ms in sorted_missing[1:]:
        if floor_to_timeframe_business(expected_next_open(prev_ts_ms, timeframe), timeframe, week_anchor_ts_ms) != timestamp_ms:
            ranges.append(GapRange(start_ts_ms=start_ts_ms, end_ts_ms=expected_next_open(prev_ts_ms, timeframe)))
            start_ts_ms = timestamp_ms
        prev_ts_ms = timestamp_ms
    ranges.append(GapRange(start_ts_ms=start_ts_ms, end_ts_ms=expected_next_open(prev_ts_ms, timeframe)))
    return ranges


def window_padding(timeframe: str, bars: int) -> int:
    if bars <= 0:
        return 0
    if is_fixed_step_timeframe(timeframe):
        return TF_TO_MS[timeframe] * bars
    if timeframe != "1M":
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    current = 0
    cursor = floor_to_timeframe(int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000), "1M")
    for _ in range(bars):
        nxt = expected_next_open(cursor, "1M")
        current += nxt - cursor
        cursor = nxt
    return current
