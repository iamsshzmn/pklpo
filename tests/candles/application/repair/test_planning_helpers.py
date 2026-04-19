from __future__ import annotations

import pytest

from src.candles.application.repair.planning import TIMEFRAME_BARS_PER_DAY, min_bars_for_window


@pytest.mark.parametrize(
    ("timeframe", "span_days", "expected_min"),
    [
        ("1m", 1, int(1440 * 1.05)),
        ("1H", 1, int(24 * 1.05)),
        ("4H", 1, int(6 * 1.05)),
        ("1D", 1, int(1 * 1.05)),
        ("1W", 7, max(1, int(1.0 * 1.05))),  # 7 days = 1 week
        ("1M", 30, max(1, int(1.0 * 1.05))),  # 30 days ~ 1 month
    ],
)
def test_min_bars_for_window_per_timeframe(
    timeframe: str,
    span_days: float,
    expected_min: int,
) -> None:
    start_ts_ms = 0
    end_ts_ms = int(span_days * 86_400_000)
    result = min_bars_for_window(start_ts_ms, end_ts_ms, timeframe)
    assert result == expected_min


def test_min_bars_for_window_minimum_is_one() -> None:
    # Zero-duration window returns 1
    assert min_bars_for_window(1000, 1000, "1m") == 1


def test_min_bars_for_window_larger_span_yields_more_bars() -> None:
    start = 0
    end_1d = 86_400_000
    end_7d = 7 * 86_400_000
    assert min_bars_for_window(start, end_7d, "1H") > min_bars_for_window(start, end_1d, "1H")


def test_timeframe_bars_per_day_covers_all_supported_timeframes() -> None:
    supported = {"1m", "1H", "4H", "1D", "1W", "1M"}
    assert supported == set(TIMEFRAME_BARS_PER_DAY.keys())


def test_timeframe_bars_per_day_values_are_positive() -> None:
    for tf, bpd in TIMEFRAME_BARS_PER_DAY.items():
        assert bpd > 0, f"{tf} bars_per_day must be positive"
