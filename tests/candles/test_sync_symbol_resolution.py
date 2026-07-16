from __future__ import annotations

import pytest

from src.candles.application.sync import (
    ExecutionMode,
    RetryPolicy,
    SyncJobRequest,
    run_candle_sync,
)


class _TelemetryRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def increment(self, metric: str, value: int | float = 1, **tags: str) -> None:
        self.events.append(
            ("metric.increment", {"metric": metric, "value": value, **tags})
        )

    def observe(self, metric: str, value: int | float, **tags: str) -> None:
        self.events.append(
            ("metric.observe", {"metric": metric, "value": value, **tags})
        )

    def event(self, name: str, **payload: object) -> None:
        self.events.append((name, payload))


class _HappyMarketData:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        return [
            {"ts": 123, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]

    async def fetch_instruments(self, instrument_type: str = "SWAP"):
        return [{"instId": "BTC-USDT-SWAP"}, {"instId": "ETH-USDT-SWAP"}]

    async def fetch_funding_rates(self, instrument_ids):
        return {symbol: {} for symbol in instrument_ids}

    async def fetch_open_interest(self, instrument_ids):
        return {symbol: {} for symbol in instrument_ids}


class _StoreOK:
    async def upsert_candles(self, **kwargs):
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str):
        return None

    async def get_fill_stats(self, start_timestamp_ms: int):
        return {"rows_today": 1}


class _CatalogPrefersRepoList:
    def __init__(self) -> None:
        self.curated_called = False
        self.refresh_called = False
        self.list_called = False

    async def load_curated_symbols(self):
        self.curated_called = True
        return ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]

    async def refresh_catalog(self):
        self.refresh_called = True
        return ["DOGE-USDT-SWAP", "SOL-USDT-SWAP"]

    async def load_cached_symbols(self):
        return ["SOL-USDT-SWAP"]

    async def list_symbols(self):
        self.list_called = True
        return ["XRP-USDT-SWAP"]


@pytest.mark.asyncio
async def test_sync_prefers_cached_repo_symbols_before_refresh_catalog() -> None:
    telemetry = _TelemetryRecorder()
    catalog = _CatalogPrefersRepoList()

    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=(),
            timeframes=("1m",),
            max_retries=0,
            max_concurrent_symbols=1,
        ),
        market_data=_HappyMarketData(),  # type: ignore[arg-type]
        candle_store=_StoreOK(),  # type: ignore[arg-type]
        instrument_catalog=catalog,  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
        telemetry=telemetry,  # type: ignore[arg-type]
    )

    assert result.total_symbols == 2
    assert result.total_symbols_processed == 2
    assert catalog.curated_called is True
    assert catalog.refresh_called is False
    assert catalog.list_called is False

    sync_started_payload = next(
        payload for name, payload in telemetry.events if name == "sync_started"
    )
    assert sync_started_payload["requested_symbols"] == 0
