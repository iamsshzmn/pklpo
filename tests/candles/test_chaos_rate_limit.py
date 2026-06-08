"""Chaos tests: API rate limit storm (mass 429).

Verifies retry behavior when the exchange API returns rate limit errors
for multiple symbols simultaneously.
"""

from __future__ import annotations

import asyncio

import pytest

from src.candles.application.sync.dto import ExecutionMode, SyncJobRequest
from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import RunCandleSyncUseCase


class _RateLimitedMarketData:
    """Returns 429 for first N calls, then succeeds."""

    def __init__(self, symbols: list[str], fail_count: int = 3) -> None:
        self._symbols = symbols
        self._fail_count = fail_count
        self._calls: dict[str, int] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        symbol = kwargs.get("instrument_id", "unknown")
        self._calls.setdefault(symbol, 0)
        self._calls[symbol] += 1
        if self._calls[symbol] <= self._fail_count:
            raise RuntimeError("429 Too Many Requests")
        return [
            {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]

    async def fetch_instruments(self, instrument_type="SWAP"):
        return [{"instId": s} for s in self._symbols]

    async def fetch_funding_rates(self, instrument_ids):
        return {}

    async def fetch_open_interest(self, instrument_ids):
        return {}

    @property
    def total_calls(self) -> int:
        return sum(self._calls.values())


class _AlwaysRateLimitedMarketData:
    """Always returns 429 — never succeeds."""

    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols
        self.call_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        self.call_count += 1
        raise RuntimeError("429 Too Many Requests")

    async def fetch_instruments(self, instrument_type="SWAP"):
        return [{"instId": s} for s in self._symbols]

    async def fetch_funding_rates(self, instrument_ids):
        return {}

    async def fetch_open_interest(self, instrument_ids):
        return {}


class _InstrumentCatalogStub:
    def __init__(self, symbols):
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
    def __init__(self):
        self.upserted = 0

    async def upsert_candles(self, **kwargs):
        self.upserted += len(kwargs["candles"])
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol, timeframe):
        return None

    async def get_fill_stats(self, start_timestamp_ms):
        return {"rows_today": 0}


@pytest.mark.asyncio
async def test_recovers_after_rate_limit_burst(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symbols get rate-limited 2 times each, then succeed on 3rd attempt."""
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep)

    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    market = _RateLimitedMarketData(symbols, fail_count=2)
    store = _CandleStoreOK()

    use_case = RunCandleSyncUseCase(
        market_data=market,
        candle_store=store,
        instrument_catalog=_InstrumentCatalogStub(symbols),
        retry_policy=RetryPolicy(max_retries=5, retry_delay=0.1, batch_size=10),
    )

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=3,
        )
    )

    assert result.total_symbols_processed == 3
    assert result.errors_count == 0
    assert store.upserted == 3  # 1 candle per symbol


@pytest.mark.asyncio
async def test_exhausts_retries_on_persistent_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If rate limiting never stops, retries are exhausted and symbols error out."""
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep)

    symbols = ["BTC-USDT-SWAP"]
    market = _AlwaysRateLimitedMarketData(symbols)
    store = _CandleStoreOK()

    use_case = RunCandleSyncUseCase(
        market_data=market,
        candle_store=store,
        instrument_catalog=_InstrumentCatalogStub(symbols),
        retry_policy=RetryPolicy(max_retries=3, retry_delay=0.1, batch_size=10),
    )

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=1,
        )
    )

    assert result.errors_count == 1
    assert result.total_symbols_processed == 0
    # Should have attempted max_retries + 1 calls
    assert market.call_count == 4  # 1 initial + 3 retries


@pytest.mark.asyncio
async def test_rate_limit_stats_tracked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate limit events are counted in endpoint_stats."""
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep)

    symbols = ["BTC-USDT-SWAP"]
    market = _RateLimitedMarketData(symbols, fail_count=2)
    store = _CandleStoreOK()

    use_case = RunCandleSyncUseCase(
        market_data=market,
        candle_store=store,
        instrument_catalog=_InstrumentCatalogStub(symbols),
        retry_policy=RetryPolicy(max_retries=5, retry_delay=0.1, batch_size=10),
    )

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=1,
        )
    )

    assert result.endpoint_stats["candles"]["rate_limit"] == 2
    assert result.endpoint_stats["candles"]["retries"] == 2
    assert result.endpoint_stats["candles"]["ok"] == 1
