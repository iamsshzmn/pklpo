"""Chaos tests: DB failure mid-batch.

Verifies that TaskGroup cancels all pending tasks when DB becomes
unavailable during an ongoing sync run.
"""

from __future__ import annotations

import asyncio

import pytest

from src.candles.application.sync.dto import ExecutionMode, SyncJobRequest
from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import (
    DatabaseUnavailableError,
    RunCandleSyncUseCase,
)


class _MarketDataStub:
    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        await asyncio.sleep(0.01)
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


class _CandleStoreFailsAfterN:
    """Fails with ConnectionRefusedError after N successful upserts."""

    def __init__(self, fail_after: int) -> None:
        self._fail_after = fail_after
        self.upsert_count = 0

    async def upsert_candles(self, **kwargs):
        self.upsert_count += 1
        if self.upsert_count > self._fail_after:
            raise ConnectionRefusedError("db went away mid-sync")
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol, timeframe):
        return None

    async def get_fill_stats(self, start_timestamp_ms):
        return {"rows_today": 0}


def _build(symbols, candle_store):
    return RunCandleSyncUseCase(
        market_data=_MarketDataStub(symbols),
        candle_store=candle_store,
        instrument_catalog=_InstrumentCatalogStub(symbols),
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
    )


@pytest.mark.asyncio
async def test_db_failure_mid_batch_aborts_all_tasks() -> None:
    """10 symbols, DB fails after 3rd upsert — should abort quickly."""
    symbols = [f"SYM{i}-USDT-SWAP" for i in range(10)]
    store = _CandleStoreFailsAfterN(fail_after=3)
    use_case = _build(symbols, store)

    with pytest.raises(DatabaseUnavailableError):
        await use_case.run(
            SyncJobRequest(
                mode=ExecutionMode.FAST,
                timeframes=("1m",),
                max_concurrent_symbols=5,
            )
        )

    # With TaskGroup, remaining tasks are cancelled immediately.
    # Far fewer than 10 upserts should have been attempted.
    assert store.upsert_count < 10


@pytest.mark.asyncio
async def test_db_failure_on_first_symbol_raises_immediately() -> None:
    """DB fails on very first upsert — should raise, not hang."""
    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    store = _CandleStoreFailsAfterN(fail_after=0)
    use_case = _build(symbols, store)

    with pytest.raises(DatabaseUnavailableError):
        await use_case.run(
            SyncJobRequest(
                mode=ExecutionMode.FAST,
                timeframes=("1m",),
                max_concurrent_symbols=2,
            )
        )


@pytest.mark.asyncio
async def test_db_failure_sequential_stops_after_first() -> None:
    """With max_concurrent=1 (sequential), second symbol should not run."""
    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    store = _CandleStoreFailsAfterN(fail_after=1)
    use_case = _build(symbols, store)

    with pytest.raises(DatabaseUnavailableError):
        await use_case.run(
            SyncJobRequest(
                mode=ExecutionMode.FAST,
                timeframes=("1m",),
                max_concurrent_symbols=1,
            )
        )

    # Only BTC should have succeeded (upsert 1), then ETH fails (upsert 2).
    # SOL should never start.
    assert store.upsert_count <= 2
