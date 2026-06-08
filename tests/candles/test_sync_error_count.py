from __future__ import annotations

import pytest

from src.candles.application.sync import (
    ExecutionMode,
    RetryPolicy,
    SyncJobRequest,
    run_candle_sync,
)


class _FailingAdapter:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        raise RuntimeError("boom")

    async def fetch_instruments(self, instrument_type: str = "SWAP"):
        return [{"instId": "BTC-USDT-SWAP"}]

    async def fetch_funding_rates(self, symbols):
        return {s: {} for s in symbols}

    async def fetch_open_interest(self, symbols):
        return {s: {} for s in symbols}


class _StoreStub:
    async def upsert_candles(self, **kwargs):
        return 0

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str):
        return None

    async def get_fill_stats(self, start_timestamp_ms: int):
        return {}


class _InstrumentCatalogStub:
    async def load_curated_symbols(self):
        return []

    async def refresh_catalog(self):
        return []

    async def load_cached_symbols(self):
        return []

    async def list_symbols(self):
        return ["BTC-USDT-SWAP"]


@pytest.mark.asyncio
async def test_sync_symbol_failure_increments_error_once() -> None:
    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            batch_size=10,
            max_retries=0,
            retry_delay=0.1,
            max_concurrent_symbols=1,
        ),
        market_data=_FailingAdapter(),  # type: ignore[arg-type]
        candle_store=_StoreStub(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalogStub(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
    )

    assert result.errors_count == 1
    assert result.total_symbols_processed == 0
