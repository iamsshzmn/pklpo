"""Tests for concurrent symbol sync — max_concurrent > 1.

Verifies:
- Correct results with 5, 10, 50 concurrent symbols
- No race conditions on shared counters
- Semaphore actually limits concurrency
"""

from __future__ import annotations

import asyncio

import pytest

from src.candles.application.sync.dto import ExecutionMode, SyncJobRequest
from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import RunCandleSyncUseCase


def _make_symbols(n: int) -> list[str]:
    return [f"SYM{i}-USDT-SWAP" for i in range(n)]


class _MarketDataStub:
    """Returns one candle per fetch, tracks concurrent call count."""

    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols
        self.max_concurrent = 0
        self._active = 0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        async with self._lock:
            self._active += 1
            if self._active > self.max_concurrent:
                self.max_concurrent = self._active
        await asyncio.sleep(0.01)
        async with self._lock:
            self._active -= 1
        return [
            {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]

    async def fetch_instruments(self, instrument_type="SWAP"):
        return [{"instId": s} for s in self._symbols]

    async def fetch_funding_rates(self, instrument_ids):
        return {}

    async def fetch_open_interest(self, instrument_ids):
        return {}


class _InstrumentCatalogStub:
    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def load_curated_symbols(self):
        return []

    async def refresh_catalog(self):
        return []

    async def load_cached_symbols(self):
        return []

    async def list_symbols(self):
        return list(self._symbols)


class _CandleStoreOK:
    def __init__(self) -> None:
        self.upserted: list[str] = []

    async def upsert_candles(self, **kwargs):
        self.upserted.append(kwargs["symbol"])
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol, timeframe):
        return None

    async def get_fill_stats(self, start_timestamp_ms):
        return {"rows_today": 0}


def _build(symbols, candle_store, max_concurrent=1):
    market = _MarketDataStub(symbols)
    return (
        RunCandleSyncUseCase(
            market_data=market,
            candle_store=candle_store,
            instrument_catalog=_InstrumentCatalogStub(symbols),
            retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
        ),
        market,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("n_symbols", "max_concurrent"), [(5, 5), (10, 5), (50, 10)])
async def test_concurrent_sync_all_symbols_processed(
    monkeypatch: pytest.MonkeyPatch,
    n_symbols: int,
    max_concurrent: int,
) -> None:
    symbols = _make_symbols(n_symbols)
    store = _CandleStoreOK()
    use_case, _market = _build(symbols, store, max_concurrent)

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=max_concurrent,
        )
    )

    assert result.total_symbols_processed == n_symbols
    assert result.rows_upserted_total == n_symbols  # 1 candle per symbol
    assert result.errors_count == 0
    assert len(store.upserted) == n_symbols


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With 20 symbols and max_concurrent=3, at most 3 should run at once."""
    symbols = _make_symbols(20)
    store = _CandleStoreOK()
    use_case, market = _build(symbols, store)

    await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=3,
        )
    )

    assert market.max_concurrent <= 3
    assert len(store.upserted) == 20
