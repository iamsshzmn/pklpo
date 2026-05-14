from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

from .repair_timeframes import (
    expected_next_open as _utc_next_open,
    floor_to_timeframe as _utc_floor,
    floor_to_timeframe_business as _utc_floor_1w,
)
from .timeframes import TF_TO_MS

_CST = timezone(timedelta(hours=8))
_CST_OFFSET_MS = 8 * 3_600_000
_DAY_MS = TF_TO_MS["1D"]
_WEEK_MS = TF_TO_MS["1W"]
_MONDAY_UTC_ANCHOR_TS_MS = int(datetime(1970, 1, 5, tzinfo=UTC).timestamp() * 1000)


class StorageCalendar:
    """PKLPO storage calendar for ``swap_ohlcv_p.timestamp``.

    Storage timestamps are always UTC bar opens:
    1H/4H use UTC fixed-hour boundaries, 1D opens at 00:00 UTC, 1W opens
    Monday 00:00 UTC, and 1M opens at month start 00:00 UTC.
    """

    def __init__(self, week_anchor_ts_ms: int | None = None) -> None:
        del week_anchor_ts_ms

    def floor_open(self, ts_ms: int, timeframe: str) -> int:
        if timeframe == "1W":
            return _utc_floor_1w(ts_ms, "1W", _MONDAY_UTC_ANCHOR_TS_MS)
        return _utc_floor(ts_ms, timeframe)

    def next_open(self, ts_ms: int, timeframe: str) -> int:
        if timeframe == "1W":
            return _utc_floor_1w(ts_ms, "1W", _MONDAY_UTC_ANCHOR_TS_MS) + _WEEK_MS
        return _utc_next_open(ts_ms, timeframe)

    def iter_opens(
        self, start_ts_ms: int, end_ts_ms: int, timeframe: str
    ) -> Iterator[int]:
        cursor = self.floor_open(start_ts_ms, timeframe)
        while cursor < end_ts_ms:
            yield cursor
            cursor = self.next_open(cursor, timeframe)


class OKXRawCalendar:
    """Exchange raw candle calendar for classic OKX SWAP bars.

    Classic OKX 1D and 1M boundaries use CST (UTC+8). Classic 1W uses the
    configured exchange week anchor. This calendar describes raw exchange
    opens only; repair/gap detection must use :class:`StorageCalendar`.
    """

    def __init__(self, week_anchor_ts_ms: int) -> None:
        self._week_anchor_ts_ms = week_anchor_ts_ms

    def floor_open(self, ts_ms: int, timeframe: str) -> int:
        if timeframe == "1D":
            return self._floor_1d(ts_ms)
        if timeframe == "1W":
            return _utc_floor_1w(ts_ms, "1W", self._week_anchor_ts_ms)
        if timeframe == "1M":
            return self._floor_1m(ts_ms)
        return _utc_floor(ts_ms, timeframe)

    def next_open(self, ts_ms: int, timeframe: str) -> int:
        if timeframe == "1D":
            return self._floor_1d(ts_ms) + _DAY_MS
        if timeframe == "1W":
            return _utc_floor_1w(ts_ms, "1W", self._week_anchor_ts_ms) + _WEEK_MS
        if timeframe == "1M":
            return self._next_1m(ts_ms)
        return _utc_next_open(ts_ms, timeframe)

    def iter_opens(
        self, start_ts_ms: int, end_ts_ms: int, timeframe: str
    ) -> Iterator[int]:
        cursor = self.floor_open(start_ts_ms, timeframe)
        while cursor < end_ts_ms:
            yield cursor
            cursor = self.next_open(cursor, timeframe)

    def _floor_1d(self, ts_ms: int) -> int:
        cst_ms = ts_ms + _CST_OFFSET_MS
        return (cst_ms // _DAY_MS) * _DAY_MS - _CST_OFFSET_MS

    def _floor_1m(self, ts_ms: int) -> int:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=_CST)
        return int(datetime(dt.year, dt.month, 1, tzinfo=_CST).timestamp() * 1000)

    def _next_1m(self, ts_ms: int) -> int:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=_CST)
        year = dt.year + (1 if dt.month == 12 else 0)
        month = 1 if dt.month == 12 else dt.month + 1
        return int(datetime(year, month, 1, tzinfo=_CST).timestamp() * 1000)


class ExchangeRawCalendar(OKXRawCalendar):
    """Named raw exchange calendar for code that should not depend on OKX naming."""


OKXCandleCalendar = StorageCalendar
