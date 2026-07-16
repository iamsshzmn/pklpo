from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.candles.application.sync.dto import ExecutionMode, SyncJobRequest
from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import RunCandleSyncUseCase, _SyncStats


@dataclass
class SyncMarketDataStub:
    candles_batches: list[list[dict[str, Any]]] = field(default_factory=list)
    instrument_rows: list[dict[str, Any]] = field(default_factory=list)
    fetch_candles_calls: list[dict[str, Any]] = field(default_factory=list)
    fetch_instruments_calls: list[str] = field(default_factory=list)

    async def __aenter__(self) -> SyncMarketDataStub:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def fetch_candles(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.fetch_candles_calls.append(kwargs)
        if self.candles_batches:
            return self.candles_batches.pop(0)
        return []

    async def fetch_instruments(
        self, instrument_type: str = "SWAP"
    ) -> list[dict[str, Any]]:
        self.fetch_instruments_calls.append(instrument_type)
        return self.instrument_rows

    async def fetch_funding_rates(
        self, instrument_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        return {}

    async def fetch_open_interest(
        self, instrument_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        return {}


@dataclass
class SyncStoreStub:
    latest_timestamp: int | None = None
    fill_stats: dict[str, int | float] = field(default_factory=dict)
    upsert_calls: list[dict[str, Any]] = field(default_factory=list)

    async def upsert_candles(self, **kwargs: Any) -> int:
        self.upsert_calls.append(kwargs)
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str) -> int | None:
        return self.latest_timestamp

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        return self.fill_stats


@dataclass
class InstrumentCatalogStub:
    curated: list[str] = field(default_factory=list)
    cached: list[str] = field(default_factory=list)
    refreshed: list[str] = field(default_factory=list)
    listed: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    async def refresh_catalog(self) -> list[str]:
        self.calls.append("refresh")
        return self.refreshed

    async def load_curated_symbols(self) -> list[str]:
        self.calls.append("curated")
        return self.curated

    async def load_cached_symbols(self) -> list[str]:
        self.calls.append("cached")
        return self.cached

    async def list_symbols(self) -> list[str]:
        self.calls.append("list")
        return self.listed


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_retries=1, retry_delay=0.1, batch_size=3, random_uniform=lambda a, b: 0.0
    )


@pytest.mark.asyncio
async def test_resolve_symbols_prefers_explicit_request() -> None:
    use_case = RunCandleSyncUseCase(
        market_data=SyncMarketDataStub(),
        candle_store=SyncStoreStub(),
        instrument_catalog=InstrumentCatalogStub(curated=["CURATED"]),
        retry_policy=_retry_policy(),
    )

    result = await use_case._resolve_symbols(("BTC-USDT-SWAP",))

    assert result == ["BTC-USDT-SWAP"]


@pytest.mark.asyncio
async def test_resolve_symbols_falls_back_to_curated_then_stops() -> None:
    catalog = InstrumentCatalogStub(
        curated=["BTC-USDT-SWAP"], cached=["CACHED"], refreshed=["REFRESHED"]
    )
    use_case = RunCandleSyncUseCase(
        market_data=SyncMarketDataStub(),
        candle_store=SyncStoreStub(),
        instrument_catalog=catalog,
        retry_policy=_retry_policy(),
    )

    result = await use_case._resolve_symbols(())

    assert result == ["BTC-USDT-SWAP"]
    assert catalog.calls == ["curated"]


@pytest.mark.asyncio
async def test_sync_bar_filters_already_stored_rows_before_upsert() -> None:
    market_data = SyncMarketDataStub(
        candles_batches=[
            [
                {"ts": "1000", "open": 1},
                {"ts": "2000", "open": 2},
                {"ts": "3000", "open": 3},
            ]
        ]
    )
    candle_store = SyncStoreStub(latest_timestamp=2000)
    use_case = RunCandleSyncUseCase(
        market_data=market_data,
        candle_store=candle_store,
        instrument_catalog=InstrumentCatalogStub(),
        retry_policy=_retry_policy(),
    )

    count, last_ts = await use_case._sync_bar(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        before=None,
        latest_stored_ts=2000,
        extra_data_loader=None,
        stats=_SyncStats(),
    )

    assert count == 1
    assert last_ts == "3000"
    assert candle_store.upsert_calls[0]["candles"] == [{"ts": "3000", "open": 3}]


@pytest.mark.asyncio
async def test_filter_supported_symbols_keeps_input_on_market_adapter_failure() -> None:
    class FailingMarketData(SyncMarketDataStub):
        async def fetch_instruments(
            self, instrument_type: str = "SWAP"
        ) -> list[dict[str, Any]]:
            raise RuntimeError("temporary failure")

    use_case = RunCandleSyncUseCase(
        market_data=FailingMarketData(),
        candle_store=SyncStoreStub(),
        instrument_catalog=InstrumentCatalogStub(),
        retry_policy=_retry_policy(),
    )

    result = await use_case._filter_supported_symbols(
        ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    )

    assert result == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]


@pytest.mark.asyncio
async def test_run_recent_sync_returns_symbol_result_without_extra_data() -> None:
    market_data = SyncMarketDataStub(
        candles_batches=[[{"ts": "1000", "open": 1}, {"ts": "2000", "open": 2}]],
        instrument_rows=[{"instId": "BTC-USDT-SWAP"}],
    )
    candle_store = SyncStoreStub(fill_stats={"fill_rate": 0.99})
    use_case = RunCandleSyncUseCase(
        market_data=market_data,
        candle_store=candle_store,
        instrument_catalog=InstrumentCatalogStub(),
        retry_policy=_retry_policy(),
    )

    result = await use_case.run(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            extra_data=False,
            batch_size=3,
            max_retries=1,
            retry_delay=0.1,
            max_concurrent_symbols=1,
        )
    )

    assert result.rows_upserted_total == 2
    assert result.total_symbols == 1
    assert result.total_symbols_processed == 1
    assert result.errors_count == 0
    assert result.results_by_symbol == {"BTC-USDT-SWAP": {"1m": 2}}
    assert candle_store.upsert_calls[0]["additional_data"] == {}
