from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, strategies as st

from src.candles.domain.repair_timeframes import (
    expected_next_open,
    floor_to_timeframe,
    is_fixed_step_timeframe,
    window_padding,
)
from src.candles.domain.timeframes import TF_TO_MS

FIXED_STEP_TIMEFRAMES = [timeframe for timeframe in TF_TO_MS if is_fixed_step_timeframe(timeframe)]


@pytest.mark.parametrize("timeframe", FIXED_STEP_TIMEFRAMES)
@given(timestamp_ms=st.integers(min_value=0, max_value=4_102_444_800_000))
def test_fixed_step_floor_and_next_open_invariant(
    timeframe: str,
    timestamp_ms: int,
) -> None:
    floored = floor_to_timeframe(timestamp_ms, timeframe)
    next_open = expected_next_open(floored, timeframe)

    assert floored <= timestamp_ms < next_open
    assert next_open - floored == TF_TO_MS[timeframe]


def test_monthly_floor_and_next_open_across_year_boundary() -> None:
    timestamp_ms = int(datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC).timestamp() * 1000)

    floored = floor_to_timeframe(timestamp_ms, "1M")
    next_open = expected_next_open(floored, "1M")

    assert floored == int(datetime(2026, 12, 1, tzinfo=UTC).timestamp() * 1000)
    assert next_open == int(datetime(2027, 1, 1, tzinfo=UTC).timestamp() * 1000)


@pytest.mark.parametrize(
    ("timeframe", "bars", "expected_ms"),
    [
        ("1m", 0, 0),
        ("1m", 3, 180_000),
        ("5m", 2, 600_000),
        ("1H", 4, 14_400_000),
    ],
)
def test_window_padding_fixed_step(timeframe: str, bars: int, expected_ms: int) -> None:
    assert window_padding(timeframe, bars) == expected_ms


def test_window_padding_monthly_uses_calendar_steps() -> None:
    jan = datetime(2026, 1, 1, tzinfo=UTC)
    feb = datetime(2026, 2, 1, tzinfo=UTC)
    mar = datetime(2026, 3, 1, tzinfo=UTC)

    assert window_padding("1M", 2) == int((feb - jan + (mar - feb)).total_seconds() * 1000)
