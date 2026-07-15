from __future__ import annotations

import pytest

from src.candles.interfaces.repair import _HistoricalRangeSourceAdapter


class _MarketDataStub:
    def __init__(self) -> None:
        self.history_calls: list[dict[str, object]] = []

    async def fetch_history_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        start_ts_ms: int,
        end_ts_ms: int,
    ):
        self.history_calls.append(
            {
                "instrument_id": instrument_id,
                "timeframe": timeframe,
                "start_ts_ms": start_ts_ms,
                "end_ts_ms": end_ts_ms,
            }
        )
        return [
            {
                "ts": 1_000,
                "open": 0.5,
                "high": 0.5,
                "low": 0.5,
                "close": 0.5,
                "volume": 5.0,
            },
            {
                "ts": 61_000,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 10.0,
            },
            {
                "ts": 121_000,
                "open": 2.0,
                "high": 2.0,
                "low": 2.0,
                "close": 2.0,
                "volume": 20.0,
            },
        ]


@pytest.mark.asyncio
async def test_historical_range_source_delegates_to_fetch_history_candles() -> None:
    stub = _MarketDataStub()
    source = _HistoricalRangeSourceAdapter(stub)  # type: ignore[arg-type]

    candles = await source.fetch_range(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=1_000,
        end_ts_ms=181_000,
    )

    assert [candle["ts"] for candle in candles] == [1_000, 61_000, 121_000]
    assert stub.history_calls == [
        {
            "instrument_id": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "start_ts_ms": 1_000,
            "end_ts_ms": 181_000,
        }
    ]


@pytest.mark.asyncio
async def test_historical_range_source_short_circuits_empty_window() -> None:
    stub = _MarketDataStub()
    source = _HistoricalRangeSourceAdapter(stub)  # type: ignore[arg-type]

    candles = await source.fetch_range(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        start_ts_ms=100,
        end_ts_ms=100,
    )

    assert candles == []
    assert stub.history_calls == []
