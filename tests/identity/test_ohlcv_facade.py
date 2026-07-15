from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _row(symbol: str, timestamp: int, close: str = "1") -> dict[str, object]:
    return {
        "series_id": symbol,
        "timeframe": "1m",
        "timestamp": timestamp,
        "open": Decimal(close),
        "high": Decimal(close),
        "low": Decimal(close),
        "close": Decimal(close),
        "volume": Decimal("10"),
        "segment_id": "raw",
        "source_venue": "OKX",
        "source_symbol": symbol,
        "source_timestamp": timestamp,
        "bar_kind": "native",
        "data_status": "complete",
        "succession_id": None,
        "adjustment_factor": Decimal("1"),
        "is_gap": False,
        "gap_type": None,
    }


@pytest.mark.asyncio
async def test_ohlcv_facade_passthrough_trivial_when_continuous_disabled() -> None:
    from src.identity.application.ohlcv_facade import OhlcvFacade

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            return series_id

        async def get_series_kind(self, series_id, as_of):
            return "trivial"

        async def read_raw(self, series_id, timeframe, start_ts, end_ts):
            return [_row(series_id, start_ts)]

        async def read_continuous(self, series_id, timeframe, start_ts, end_ts):
            raise AssertionError("trivial series must read raw passthrough")

        async def read_gap_markers(self, series_id, timeframe, start_ts, end_ts, as_of):
            return []

        async def get_adjustment_factor(self, series_id, timestamp, as_of):
            return Decimal("1")

    rows = await OhlcvFacade(_Repository(), continuous_read_enabled=False).read_ohlcv(
        series_id="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts=1000,
        end_ts=2000,
        as_of=_ts("2026-07-03T00:00:00+00:00"),
    )

    assert len(rows) == 1
    assert rows[0].series_id == "BTC-USDT-SWAP"
    assert rows[0].bar_kind == "native"
    assert rows[0].adjustment_factor == Decimal("1")
    assert rows[0].succession_id is None
    assert rows[0].is_gap is False


@pytest.mark.asyncio
async def test_ohlcv_facade_fails_closed_for_composite_when_disabled() -> None:
    from src.identity.application.ohlcv_facade import (
        ContinuousReadDisabledError,
        OhlcvFacade,
    )

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            return series_id

        async def get_series_kind(self, series_id, as_of):
            return "composite"

    with pytest.raises(ContinuousReadDisabledError):
        await OhlcvFacade(_Repository(), continuous_read_enabled=False).read_ohlcv(
            series_id="TON-USDT-SWAP",
            timeframe="1m",
            start_ts=1000,
            end_ts=2000,
            as_of=_ts("2026-07-03T00:00:00+00:00"),
        )


@pytest.mark.asyncio
async def test_ohlcv_facade_reads_pit_alias_from_continuous_and_applies_adjustment() -> (
    None
):
    from src.identity.application.ohlcv_facade import OhlcvFacade

    calls = []

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            assert series_id == "GRAM-USDT-SWAP"
            return "TON-USDT-SWAP"

        async def get_series_kind(self, series_id, as_of):
            assert series_id == "TON-USDT-SWAP"
            return "composite"

        async def read_continuous(self, series_id, timeframe, start_ts, end_ts):
            calls.append((series_id, timeframe, start_ts, end_ts))
            raw = _row("TON-USDT-SWAP", start_ts, close="2")
            raw["source_symbol"] = "GRAM-USDT-SWAP"
            raw["succession_id"] = "lineage"
            return [raw]

        async def read_raw(self, series_id, timeframe, start_ts, end_ts):
            raise AssertionError(
                "composite series must read continuous materialization"
            )

        async def read_gap_markers(self, series_id, timeframe, start_ts, end_ts, as_of):
            return []

        async def get_adjustment_factor(self, series_id, timestamp, as_of):
            return Decimal("1.5")

    rows = await OhlcvFacade(_Repository(), continuous_read_enabled=True).read_ohlcv(
        series_id="GRAM-USDT-SWAP",
        timeframe="1m",
        start_ts=1000,
        end_ts=2000,
        as_of=_ts("2026-07-03T00:00:00+00:00"),
    )

    assert calls == [("TON-USDT-SWAP", "1m", 1000, 2000)]
    assert rows[0].series_id == "TON-USDT-SWAP"
    assert rows[0].source_symbol == "GRAM-USDT-SWAP"
    assert rows[0].close == Decimal("3.0")
    assert rows[0].adjustment_factor == Decimal("1.5")


@pytest.mark.asyncio
async def test_ohlcv_facade_returns_gap_markers_only_when_requested() -> None:
    from src.identity.application.ohlcv_facade import OhlcvFacade

    class _Repository:
        async def resolve_alias(self, series_id, as_of):
            return series_id

        async def get_series_kind(self, series_id, as_of):
            return "composite"

        async def read_continuous(self, series_id, timeframe, start_ts, end_ts):
            return [_row(series_id, 3000)]

        async def read_raw(self, series_id, timeframe, start_ts, end_ts):
            return []

        async def read_gap_markers(self, series_id, timeframe, start_ts, end_ts, as_of):
            return [
                {
                    "series_id": series_id,
                    "timeframe": timeframe,
                    "timestamp": 2000,
                    "gap_type": "migration_halt",
                    "segment_id": "gap",
                }
            ]

        async def get_adjustment_factor(self, series_id, timestamp, as_of):
            return Decimal("1")

    rows_without_gaps = await OhlcvFacade(
        _Repository(), continuous_read_enabled=True
    ).read_ohlcv(
        series_id="TON-USDT-SWAP",
        timeframe="1m",
        start_ts=1000,
        end_ts=4000,
        as_of=_ts("2026-07-03T00:00:00+00:00"),
        include_gap_markers=False,
    )
    rows_with_gaps = await OhlcvFacade(
        _Repository(), continuous_read_enabled=True
    ).read_ohlcv(
        series_id="TON-USDT-SWAP",
        timeframe="1m",
        start_ts=1000,
        end_ts=4000,
        as_of=_ts("2026-07-03T00:00:00+00:00"),
        include_gap_markers=True,
    )

    assert [row.is_gap for row in rows_without_gaps] == [False]
    assert [(row.timestamp, row.is_gap, row.gap_type) for row in rows_with_gaps] == [
        (2000, True, "migration_halt"),
        (3000, False, None),
    ]
