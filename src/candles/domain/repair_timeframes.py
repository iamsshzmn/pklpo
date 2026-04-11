from __future__ import annotations

from datetime import UTC, datetime

from .timeframes import TF_TO_MS


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
