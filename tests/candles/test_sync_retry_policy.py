from __future__ import annotations

import pytest

from src.candles.application.sync import (
    ExecutionMode,
    RetryPolicy,
    SyncJobRequest,
    run_candle_sync,
)


class _StoreOK:
    async def upsert_candles(self, **kwargs):
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str):
        return None

    async def get_fill_stats(self, start_timestamp_ms: int):
        return {"rows_today": 1}


class _InstrumentCatalog:
    async def load_curated_symbols(self):
        return []

    async def refresh_catalog(self):
        return []

    async def load_cached_symbols(self):
        return []

    async def list_symbols(self):
        return ["BTC-USDT-SWAP"]


class _BaseMarketData:
    def __init__(self) -> None:
        self.fetch_candles_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_instruments(self, instrument_type: str = "SWAP"):
        return [{"instId": "BTC-USDT-SWAP"}]

    async def fetch_funding_rates(self, instrument_ids):
        return {symbol: {} for symbol in instrument_ids}

    async def fetch_open_interest(self, instrument_ids):
        return {symbol: {} for symbol in instrument_ids}


class _TimeoutThenSuccessMarketData(_BaseMarketData):
    async def fetch_candles(self, **kwargs):
        self.fetch_candles_calls += 1
        if self.fetch_candles_calls == 1:
            raise TimeoutError("request timed out")
        return [
            {"ts": 123, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]


class _RateLimitThenSuccessMarketData(_BaseMarketData):
    async def fetch_candles(self, **kwargs):
        self.fetch_candles_calls += 1
        if self.fetch_candles_calls == 1:
            raise RuntimeError("429 Too Many Requests")
        return [
            {"ts": 123, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]


class _FatalMarketData(_BaseMarketData):
    async def fetch_candles(self, **kwargs):
        self.fetch_candles_calls += 1
        raise ValueError("bad candle payload")


@pytest.mark.asyncio
async def test_timeout_failure_is_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )

    market = _TimeoutThenSuccessMarketData()
    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            max_retries=1,
            retry_delay=0.01,
            max_concurrent_symbols=1,
        ),
        market_data=market,  # type: ignore[arg-type]
        candle_store=_StoreOK(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalog(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=1, retry_delay=0.01, batch_size=10),
    )

    assert market.fetch_candles_calls == 2
    assert result.errors_count == 0
    assert result.endpoint_stats["candles"]["retries"] == 1
    assert result.endpoint_stats["candles"]["rate_limit"] == 0
    assert result.endpoint_stats["candles"]["timeout"] == 1


@pytest.mark.asyncio
async def test_rate_limit_failure_still_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )

    market = _RateLimitThenSuccessMarketData()
    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            max_retries=1,
            retry_delay=0.01,
            max_concurrent_symbols=1,
        ),
        market_data=market,  # type: ignore[arg-type]
        candle_store=_StoreOK(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalog(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=1, retry_delay=0.01, batch_size=10),
    )

    assert market.fetch_candles_calls == 2
    assert result.errors_count == 0
    assert result.endpoint_stats["candles"]["retries"] == 1
    assert result.endpoint_stats["candles"]["rate_limit"] == 1
    assert result.endpoint_stats["candles"]["timeout"] == 0


@pytest.mark.asyncio
async def test_non_retriable_failure_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )

    market = _FatalMarketData()
    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            max_retries=5,
            retry_delay=0.01,
            max_concurrent_symbols=1,
        ),
        market_data=market,  # type: ignore[arg-type]
        candle_store=_StoreOK(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalog(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=5, retry_delay=0.01, batch_size=10),
    )

    assert market.fetch_candles_calls == 1
    assert result.errors_count == 1
    assert result.total_symbols_processed == 0
    assert result.endpoint_stats["candles"]["retries"] == 0
    assert result.endpoint_stats["candles"]["timeout"] == 0
