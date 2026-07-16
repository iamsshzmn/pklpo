from __future__ import annotations

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

    async def __aenter__(self) -> _MarketDataStub:
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def fetch_candles(self, **kwargs):
        return [
            {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]

    async def fetch_instruments(self, instrument_type: str = "SWAP"):
        return [{"instId": symbol} for symbol in self._symbols]

    async def fetch_funding_rates(self, instrument_ids: list[str]):
        return {symbol: {} for symbol in instrument_ids}

    async def fetch_open_interest(self, instrument_ids: list[str]):
        return {symbol: {} for symbol in instrument_ids}


class _InstrumentCatalogStub:
    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def load_curated_symbols(self) -> list[str]:
        return []

    async def refresh_catalog(self) -> list[str]:
        return []

    async def load_cached_symbols(self) -> list[str]:
        return []

    async def list_symbols(self) -> list[str]:
        return list(self._symbols)


class _CandleStoreProbeFailure:
    async def upsert_candles(self, **kwargs):
        return 0

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str) -> int | None:
        return None

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        raise ConnectionRefusedError("db unavailable")


class _CandleStoreFailFirstSymbol:
    def __init__(self) -> None:
        self.seen_symbols: list[str] = []

    async def upsert_candles(self, **kwargs):
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str) -> int | None:
        self.seen_symbols.append(symbol)
        if symbol == "BTC-USDT-SWAP":
            raise ConnectionRefusedError("db unavailable")
        return None

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        return {"rows_today": 0}


class _CandleStoreNonDbFailure:
    def __init__(self) -> None:
        self.upsert_symbols: list[str] = []

    async def upsert_candles(self, **kwargs):
        symbol = kwargs["symbol"]
        self.upsert_symbols.append(symbol)
        if symbol == "BTC-USDT-SWAP":
            raise ValueError("bad candle payload")
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str) -> int | None:
        return None

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        return {"rows_today": 1}


def _build_use_case(symbols: list[str], candle_store) -> RunCandleSyncUseCase:
    return RunCandleSyncUseCase(
        market_data=_MarketDataStub(symbols),
        candle_store=candle_store,
        instrument_catalog=_InstrumentCatalogStub(symbols),
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
    )


@pytest.mark.asyncio
async def test_run_fails_fast_when_db_probe_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )
    use_case = _build_use_case(["BTC-USDT-SWAP"], _CandleStoreProbeFailure())

    with pytest.raises(DatabaseUnavailableError, match="database_unavailable"):
        await use_case.run(
            SyncJobRequest(mode=ExecutionMode.FAST, max_concurrent_symbols=1)
        )


@pytest.mark.asyncio
async def test_run_stops_processing_new_symbols_after_db_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    candle_store = _CandleStoreFailFirstSymbol()
    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )
    use_case = _build_use_case(["BTC-USDT-SWAP", "ETH-USDT-SWAP"], candle_store)

    with pytest.raises(DatabaseUnavailableError, match="database_unavailable"):
        await use_case.run(
            SyncJobRequest(mode=ExecutionMode.FAST, max_concurrent_symbols=1)
        )

    assert candle_store.seen_symbols == ["BTC-USDT-SWAP"]


@pytest.mark.asyncio
async def test_non_db_symbol_error_does_not_abort_entire_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    candle_store = _CandleStoreNonDbFailure()
    monkeypatch.setattr(
        "src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep
    )
    use_case = _build_use_case(["BTC-USDT-SWAP", "ETH-USDT-SWAP"], candle_store)

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST, timeframes=("1m",), max_concurrent_symbols=1
        )
    )

    assert result.errors_count == 1
    assert result.total_symbols_processed == 1
    assert result.rows_upserted_total == 1
    assert candle_store.upsert_symbols == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
