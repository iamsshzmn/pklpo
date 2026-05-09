from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.candles.application.repair.planning import (
    TIMEFRAME_BARS_PER_DAY,
    min_bars_for_window,
    plan_tail_first_repair,
)
from src.candles.domain.okx_calendar import OKXCandleCalendar


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
    assert min_bars_for_window(start, end_7d, "1H") > min_bars_for_window(
        start, end_1d, "1H"
    )


def test_timeframe_bars_per_day_covers_all_supported_timeframes() -> None:
    supported = {"1m", "1H", "4H", "1D", "1W", "1M"}
    assert supported == set(TIMEFRAME_BARS_PER_DAY.keys())


def test_timeframe_bars_per_day_values_are_positive() -> None:
    for tf, bpd in TIMEFRAME_BARS_PER_DAY.items():
        assert bpd > 0, f"{tf} bars_per_day must be positive"


@pytest.mark.asyncio
async def test_plan_tail_first_repair_1m_no_phantom_gap() -> None:
    """1M with max_range_days=7: trailing window lands mid-month.

    Before the fix, detect_gap_tasks started at a non-bar boundary (e.g.
    April 24) and reported a phantom gap.  After the fix, start_ts_ms is
    snapped to the nearest 1M boundary so the planning window always starts
    at a real bar position, yielding no gaps when coverage is complete.
    """
    # May 8, 2026 14:08 UTC — real run timestamp from log
    now_ts_ms = 1_778_248_080_000

    # OKX calendar: 1M floor uses CST (UTC+8) month boundary.
    # May 8 22:08 CST → May 1 00:00 CST = April 30 16:00 UTC = 1_777_564_800_000.
    cal = OKXCandleCalendar(week_anchor_ts_ms=0)
    closed_until = cal.floor_open(now_ts_ms, "1M")  # April 30 16:00 UTC

    # Coverage mock: bar stored at May 1 00:00 UTC (within the trailing window)
    may_1_utc_ms = 1_777_593_600_000
    coverage_query = AsyncMock()
    coverage_query.get_coverage_bounds.return_value = (may_1_utc_ms, may_1_utc_ms)
    coverage_query.list_timestamps.return_value = [may_1_utc_ms]

    plan = await plan_tail_first_repair(
        coverage_query=coverage_query,
        symbol="BTC-USDT-SWAP",
        timeframe="1M",
        max_range_days=7,
        now_ts_ms=now_ts_ms,
        chunk_size_bars=250,
        anchor_ts_ms=None,
        anchor_strategy="first-coverage",
        anchor_metadata=None,
        calendar=cal,
    )

    assert plan.closed_until_ts_ms == closed_until
    # The planning window must start exactly at a CST-aligned 1M bar boundary
    assert plan.start_ts_ms == cal.floor_open(plan.start_ts_ms, "1M"), (
        "planning window start must be aligned to 1M bar boundary"
    )
    # Complete coverage → no gaps → loop breaks on first iteration
    assert plan.gaps == (), f"expected no gaps, got {plan.gaps}"
