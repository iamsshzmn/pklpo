from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, strategies as st

from src.candles.domain.okx_calendar import OKXRawCalendar, StorageCalendar
from src.candles.domain.repair import GapRange
from src.candles.domain.repair_timeframes import (
    build_last_n_closed_window,
    expected_next_open,
    floor_to_timeframe,
    floor_to_timeframe_business,
    is_fixed_step_timeframe,
    list_expected_timestamps,
    merge_adjacent_timestamps,
    window_padding,
)
from src.candles.domain.timeframes import TF_TO_MS

FIXED_STEP_TIMEFRAMES = [timeframe for timeframe in TF_TO_MS if is_fixed_step_timeframe(timeframe)]

UTC_CAL = StorageCalendar()


def _ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=UTC).timestamp() * 1000)


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


def test_build_last_n_closed_window_excludes_current_open_bar_for_fixed_step() -> None:
    now_ts_ms = _ts(2026, 4, 11, 12, 3)

    window_start, closed_until = build_last_n_closed_window(
        now_ts_ms,
        "1m",
        bars=3,
        week_anchor_ts_ms=0,
        calendar=UTC_CAL,
    )

    assert window_start == _ts(2026, 4, 11, 12, 0)
    assert closed_until == _ts(2026, 4, 11, 12, 3)


def test_build_last_n_closed_window_uses_storage_monday_weekly_flooring() -> None:
    now_ts_ms = _ts(2026, 1, 23, 12)

    window_start, closed_until = build_last_n_closed_window(
        now_ts_ms,
        "1W",
        bars=2,
        week_anchor_ts_ms=0,
        calendar=UTC_CAL,
    )

    assert window_start == _ts(2026, 1, 5)
    assert closed_until == _ts(2026, 1, 19)


def test_floor_to_timeframe_business_delegates_non_weekly_timeframes() -> None:
    assert floor_to_timeframe_business(_ts(2026, 4, 11, 12, 3), "1m", 0) == _ts(
        2026, 4, 11, 12, 3
    )


def test_list_expected_timestamps_returns_fixed_step_opens() -> None:
    expected = list_expected_timestamps(
        _ts(2026, 4, 11, 12, 0),
        _ts(2026, 4, 11, 12, 3),
        "1m",
        calendar=UTC_CAL,
    )

    assert expected == [
        _ts(2026, 4, 11, 12, 0),
        _ts(2026, 4, 11, 12, 1),
        _ts(2026, 4, 11, 12, 2),
    ]


def test_list_expected_timestamps_steps_by_storage_calendar_for_months() -> None:
    expected = list_expected_timestamps(
        _ts(2026, 1, 1),
        _ts(2026, 4, 1),
        "1M",
        calendar=UTC_CAL,
    )

    assert expected == [
        _ts(2026, 1, 1),
        _ts(2026, 2, 1),
        _ts(2026, 3, 1),
    ]


def test_merge_adjacent_timestamps_merges_expected_storage_months() -> None:
    merged = merge_adjacent_timestamps(
        [_ts(2026, 1, 1), _ts(2026, 2, 1), _ts(2026, 4, 1)],
        "1M",
        week_anchor_ts_ms=0,
        calendar=UTC_CAL,
    )

    assert merged == [
        GapRange(start_ts_ms=_ts(2026, 1, 1), end_ts_ms=_ts(2026, 3, 1)),
        GapRange(start_ts_ms=_ts(2026, 4, 1), end_ts_ms=_ts(2026, 5, 1)),
    ]


def test_raw_calendar_keeps_okx_cst_month_semantics_separate() -> None:
    raw_cal = OKXRawCalendar(week_anchor_ts_ms=0)

    expected = list_expected_timestamps(
        _ts(2025, 12, 31, 16),
        _ts(2026, 3, 31, 16),
        "1M",
        calendar=raw_cal,
    )

    assert expected == [
        _ts(2025, 12, 31, 16),
        _ts(2026, 1, 31, 16),
        _ts(2026, 2, 28, 16),
    ]


def test_merge_adjacent_timestamps_merges_weekly_ranges_with_raw_anchor() -> None:
    anchor_ts_ms = _ts(2026, 1, 7)
    raw_cal = OKXRawCalendar(week_anchor_ts_ms=anchor_ts_ms)
    merged = merge_adjacent_timestamps(
        [_ts(2026, 1, 7), _ts(2026, 1, 14), _ts(2026, 1, 28)],
        "1W",
        week_anchor_ts_ms=anchor_ts_ms,
        calendar=raw_cal,
    )

    assert merged == [
        GapRange(start_ts_ms=_ts(2026, 1, 7), end_ts_ms=_ts(2026, 1, 21)),
        GapRange(start_ts_ms=_ts(2026, 1, 28), end_ts_ms=_ts(2026, 2, 4)),
    ]


def test_window_padding_for_months_uses_safe_upper_bound() -> None:
    assert window_padding("1M", 2) == 62 * 86_400_000


@pytest.mark.parametrize("bars", [0, -1])
def test_build_last_n_closed_window_rejects_non_positive_bars(bars: int) -> None:
    with pytest.raises(ValueError, match="bars must be >= 1"):
        build_last_n_closed_window(
            _ts(2026, 4, 11, 12, 3),
            "1m",
            bars=bars,
            week_anchor_ts_ms=0,
            calendar=UTC_CAL,
        )
