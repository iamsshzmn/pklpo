"""Chaos tests: partial row failure in batch.

Verifies that upsert errors are properly propagated and don't
corrupt counters or leave the sync in an inconsistent state.
"""

from __future__ import annotations

import pytest

from src.candles.application.sync.dto import ExecutionMode, SyncJobRequest
from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import RunCandleSyncUseCase


class _MarketDataStub:
    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        return [
            {"ts": i, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}
            for i in range(5)
        ]

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


class _CandleStorePartialFailure:
    """Fails on upsert for specific symbols, succeeds for others."""

    def __init__(self, fail_symbols: set[str]) -> None:
        self._fail_symbols = fail_symbols
        self.success_symbols: list[str] = []

    async def upsert_candles(self, **kwargs):
        symbol = kwargs["symbol"]
        if symbol in self._fail_symbols:
            raise ValueError(f"integrity violation for {symbol}")
        self.success_symbols.append(symbol)
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol, timeframe):
        return None

    async def get_fill_stats(self, start_timestamp_ms):
        return {"rows_today": 0}


class _CandleStoreRowCountMismatch:
    """Returns fewer rows than expected from upsert."""

    def __init__(self) -> None:
        self.symbols_seen: list[str] = []

    async def upsert_candles(self, **kwargs):
        self.symbols_seen.append(kwargs["symbol"])
        # Claim only 1 row was written when 5 were sent
        return 1

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
async def test_partial_failure_continues_other_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BTC fails on upsert, but ETH and SOL should still succeed."""

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )

    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
    store = _CandleStorePartialFailure(fail_symbols={"BTC-USDT-SWAP"})
    use_case = _build(symbols, store)

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=1,
        )
    )

    assert result.errors_count == 1
    assert result.total_symbols_processed == 2
    assert sorted(store.success_symbols) == ["ETH-USDT-SWAP", "SOL-USDT-SWAP"]


@pytest.mark.asyncio
async def test_all_symbols_fail_on_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All symbols fail — errors_count matches, no rows upserted."""

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )

    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    store = _CandleStorePartialFailure(fail_symbols=set(symbols))
    use_case = _build(symbols, store)

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=1,
        )
    )

    assert result.errors_count == 2
    assert result.total_symbols_processed == 0
    assert result.rows_upserted_total == 0


@pytest.mark.asyncio
async def test_row_count_mismatch_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When upsert returns fewer rows, the count should reflect reality."""

    async def _no_sleep(_):
        return None

    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )

    symbols = ["BTC-USDT-SWAP"]
    store = _CandleStoreRowCountMismatch()
    use_case = _build(symbols, store)

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            timeframes=("1m",),
            max_concurrent_symbols=1,
        )
    )

    # Use case counts what upsert_candles returns (1), not what was sent (5)
    assert result.rows_upserted_total == 1
    assert result.total_symbols_processed == 1
