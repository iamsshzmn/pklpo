from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.candles.domain.okx_calendar import OKXRawCalendar, StorageCalendar

UTC = UTC
CST = timezone(timedelta(hours=8))

# ADR default: 2026-05-03T16:00:00Z = Sunday 16:00 UTC = Monday 00:00 CST
WEEK_ANCHOR = 1777824000000


@pytest.fixture
def raw_cal() -> OKXRawCalendar:
    return OKXRawCalendar(week_anchor_ts_ms=WEEK_ANCHOR)


@pytest.fixture
def storage_cal() -> StorageCalendar:
    return StorageCalendar()


def _ts(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def test_raw_floor_1d_mid_day_returns_cst_midnight(
    raw_cal: OKXRawCalendar,
) -> None:
    ts = _ts(datetime(2026, 5, 9, 18, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert raw_cal.floor_open(ts, "1D") == expected


def test_raw_floor_1d_on_boundary_is_idempotent(raw_cal: OKXRawCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert raw_cal.floor_open(ts, "1D") == ts


def test_raw_floor_1d_before_boundary_floors_to_previous(
    raw_cal: OKXRawCalendar,
) -> None:
    ts = _ts(datetime(2026, 5, 9, 10, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 8, 16, 0, tzinfo=UTC))
    assert raw_cal.floor_open(ts, "1D") == expected


def test_raw_next_open_1d_advances_one_day(raw_cal: OKXRawCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert raw_cal.next_open(ts, "1D") == ts + 86_400_000


def test_storage_floor_1d_uses_utc_midnight(storage_cal: StorageCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 18, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 9, 0, 0, tzinfo=UTC))
    assert storage_cal.floor_open(ts, "1D") == expected


def test_raw_floor_1w_on_anchor_is_idempotent(raw_cal: OKXRawCalendar) -> None:
    assert raw_cal.floor_open(WEEK_ANCHOR, "1W") == WEEK_ANCHOR


def test_raw_floor_1w_mid_week_returns_anchor(raw_cal: OKXRawCalendar) -> None:
    ts = WEEK_ANCHOR + 3 * 86_400_000
    assert raw_cal.floor_open(ts, "1W") == WEEK_ANCHOR


def test_raw_next_open_1w_advances_one_week(raw_cal: OKXRawCalendar) -> None:
    assert raw_cal.next_open(WEEK_ANCHOR, "1W") == WEEK_ANCHOR + 604_800_000


def test_storage_floor_1w_uses_monday_utc(storage_cal: StorageCalendar) -> None:
    ts = _ts(datetime(2026, 5, 14, 12, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 11, 0, 0, tzinfo=UTC))
    assert storage_cal.floor_open(ts, "1W") == expected


def test_raw_floor_1m_mid_month_returns_cst_month_start(
    raw_cal: OKXRawCalendar,
) -> None:
    ts = _ts(datetime(2026, 5, 15, 4, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 4, 30, 16, 0, tzinfo=UTC))
    assert raw_cal.floor_open(ts, "1M") == expected


def test_raw_floor_1m_on_boundary_is_idempotent(raw_cal: OKXRawCalendar) -> None:
    ts = _ts(datetime(2026, 4, 30, 16, 0, tzinfo=UTC))
    assert raw_cal.floor_open(ts, "1M") == ts


def test_raw_next_open_1m_december_wraps_to_january(
    raw_cal: OKXRawCalendar,
) -> None:
    dec_start = _ts(datetime(2025, 12, 1, tzinfo=CST))
    jan_start = _ts(datetime(2026, 1, 1, tzinfo=CST))
    assert raw_cal.next_open(dec_start, "1M") == jan_start


def test_storage_floor_1m_uses_utc_month_start(storage_cal: StorageCalendar) -> None:
    ts = _ts(datetime(2026, 5, 15, 4, 0, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 1, 0, 0, tzinfo=UTC))
    assert storage_cal.floor_open(ts, "1M") == expected


def test_raw_floor_1h_delegates_to_utc(raw_cal: OKXRawCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 14, 35, tzinfo=UTC))
    expected = _ts(datetime(2026, 5, 9, 14, 0, tzinfo=UTC))
    assert raw_cal.floor_open(ts, "1H") == expected


def test_raw_next_open_1h_delegates_to_utc(raw_cal: OKXRawCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 14, 0, tzinfo=UTC))
    assert raw_cal.next_open(ts, "1H") == ts + 3_600_000


def test_raw_iter_opens_1d_returns_three_opens(raw_cal: OKXRawCalendar) -> None:
    start = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    end = _ts(datetime(2026, 5, 12, 16, 0, tzinfo=UTC))
    opens = list(raw_cal.iter_opens(start, end, "1D"))
    assert opens == [start, start + 86_400_000, start + 2 * 86_400_000]


def test_raw_iter_opens_empty_when_start_ge_end(raw_cal: OKXRawCalendar) -> None:
    ts = _ts(datetime(2026, 5, 9, 16, 0, tzinfo=UTC))
    assert list(raw_cal.iter_opens(ts, ts, "1D")) == []
