from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.candles.domain.okx_calendar import OKXCandleCalendar

UTC = UTC
CST = timezone(timedelta(hours=8))

# ADR default: 2026-05-03T16:00:00Z = Sunday 16:00 UTC = Monday 00:00 CST
WEEK_ANCHOR = 1777824000000


@pytest.fixture
def cal() -> OKXCandleCalendar:
    return OKXCandleCalendar(week_anchor_ts_ms=WEEK_ANCHOR)


def _ts(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


# --- 1D ---


def test_floor_1d_mid_day_returns_cst_midnight(cal: OKXCandleCalendar) -> None:
    # 2026-05-09 18:00 UTC → floor to 2026-05-09 16:00 UTC (= 2026-05-10 00:00 CST)
    ts = _ts(datetime(2026, 5, 9, 18, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert cal.floor_open(ts, "1D") == expected


def test_floor_1d_on_boundary_is_idempotent(cal: OKXCandleCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert cal.floor_open(ts, "1D") == ts


def test_floor_1d_before_boundary_floors_to_previous(cal: OKXCandleCalendar) -> None:
    # 2026-05-09 10:00 UTC → still 2026-05-08 16:00 UTC (= 2026-05-09 00:00 CST)
    ts = _ts(datetime(2026, 5, 9, 10, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 8, 16, 0, tzinfo=UTC))
    assert cal.floor_open(ts, "1D") == expected


def test_next_open_1d_advances_one_day(cal: OKXCandleCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert cal.next_open(ts, "1D") == ts + 86_400_000


# --- 1W ---


def test_floor_1w_on_anchor_is_idempotent(cal: OKXCandleCalendar) -> None:
    assert cal.floor_open(WEEK_ANCHOR, "1W") == WEEK_ANCHOR


def test_floor_1w_mid_week_returns_anchor(cal: OKXCandleCalendar) -> None:
    ts = WEEK_ANCHOR + 3 * 86_400_000  # 3 days after anchor
    assert cal.floor_open(ts, "1W") == WEEK_ANCHOR


def test_next_open_1w_advances_one_week(cal: OKXCandleCalendar) -> None:
    assert cal.next_open(WEEK_ANCHOR, "1W") == WEEK_ANCHOR + 604_800_000


# --- 1M ---


def test_floor_1m_mid_month_returns_cst_month_start(cal: OKXCandleCalendar) -> None:
    # 2026-05-15 04:00 UTC = 2026-05-15 12:00 CST → floor to 2026-05-01 00:00 CST = 2026-04-30 16:00 UTC
    ts = _ts(datetime(2026, 5, 15, 4, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 4, 30, 16, 0, tzinfo=UTC))
    assert cal.floor_open(ts, "1M") == expected


def test_floor_1m_on_boundary_is_idempotent(cal: OKXCandleCalendar) -> None:
    ts = _ts(datetime(2026, 4, 30, 16, 0, tzinfo=UTC))  # = 2026-05-01 00:00 CST
    assert cal.floor_open(ts, "1M") == ts


def test_next_open_1m_december_wraps_to_january(cal: OKXCandleCalendar) -> None:
    dec_start = _ts(datetime(2025, 12, 1, tzinfo=CST))
    jan_start = _ts(datetime(2026, 1, 1, tzinfo=CST))
    assert cal.next_open(dec_start, "1M") == jan_start


# --- UTC delegation ---


def test_floor_1h_delegates_to_utc(cal: OKXCandleCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 14, 35, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 9, 14, 0, tzinfo=UTC))
    assert cal.floor_open(ts, "1H") == expected


def test_next_open_1h_delegates_to_utc(cal: OKXCandleCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 14, 0, tzinfo=UTC))
    assert cal.next_open(ts, "1H") == ts + 3_600_000


# --- iter_opens ---


def test_iter_opens_1d_returns_three_opens(cal: OKXCandleCalendar) -> None:
    start = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    end = _ts(datetime(2026, 5, 12, 16, 0, tzinfo=UTC))
    opens = list(cal.iter_opens(start, end, "1D"))
    assert opens == [start, start + 86_400_000, start + 2 * 86_400_000]


def test_iter_opens_empty_when_start_ge_end(cal: OKXCandleCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert list(cal.iter_opens(ts, ts, "1D")) == []
