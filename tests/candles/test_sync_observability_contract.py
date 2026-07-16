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
        return [{"instId": "BTC-USDT-SWAP"}]

    async def fetch_funding_rates(self, instrument_ids):
        return {symbol: {} for symbol in instrument_ids}

    async def fetch_open_interest(self, instrument_ids):
        return {symbol: {} for symbol in instrument_ids}


class _RetryingMarketData(_HappyMarketData):
    def __init__(self) -> None:
        self._calls = 0

    async def fetch_candles(self, **kwargs):
        self._calls += 1
        if self._calls == 1:
            raise RuntimeError("429 Too Many Requests")
        return await super().fetch_candles(**kwargs)


class _StoreOK:
    async def upsert_candles(self, **kwargs):
        return len(kwargs["candles"])

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str):
        return None

    async def get_fill_stats(self, start_timestamp_ms: int):
        return {"rows_today": 1}


class _StoreFailsUpsert(_StoreOK):
    async def upsert_candles(self, **kwargs):
        raise RuntimeError("db write failed")


class _InstrumentCatalog:
    async def load_curated_symbols(self):
        return []

    async def refresh_catalog(self):
        return []

    async def load_cached_symbols(self):
        return []

    async def list_symbols(self):
        return ["BTC-USDT-SWAP"]


def _event_names(recorder: _TelemetryRecorder) -> list[str]:
    return [name for name, _ in recorder.events]


@pytest.mark.asyncio
async def test_sync_emits_required_run_events() -> None:
    telemetry = _TelemetryRecorder()

    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            max_retries=0,
            max_concurrent_symbols=1,
        ),
        market_data=_HappyMarketData(),  # type: ignore[arg-type]
        candle_store=_StoreOK(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalog(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
        telemetry=telemetry,  # type: ignore[arg-type]
    )

    names = _event_names(telemetry)
    assert names[0] == "sync_started"
    assert "symbol_started" in names
    assert "symbol_completed" in names
    assert names[-1] == "sync_completed"
    assert result.sync_run is not None
    assert result.sync_run.status.value == "completed"


@pytest.mark.asyncio
async def test_sync_emits_fetch_retried_event() -> None:
    telemetry = _TelemetryRecorder()

    await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            max_retries=1,
            retry_delay=0.01,
            max_concurrent_symbols=1,
        ),
        market_data=_RetryingMarketData(),  # type: ignore[arg-type]
        candle_store=_StoreOK(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalog(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=1, retry_delay=0.01, batch_size=10),
        telemetry=telemetry,  # type: ignore[arg-type]
    )

    assert "fetch_retried" in _event_names(telemetry)


@pytest.mark.asyncio
async def test_sync_emits_upsert_failed_event() -> None:
    telemetry = _TelemetryRecorder()

    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            max_retries=0,
            max_concurrent_symbols=1,
        ),
        market_data=_HappyMarketData(),  # type: ignore[arg-type]
        candle_store=_StoreFailsUpsert(),  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalog(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
        telemetry=telemetry,  # type: ignore[arg-type]
    )

    assert "upsert_failed" in _event_names(telemetry)
    assert result.errors_count == 1
