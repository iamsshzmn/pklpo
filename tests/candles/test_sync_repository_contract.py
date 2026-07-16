from __future__ import annotations

from datetime import UTC

import pytest

from src.candles.application.sync import (
    ExecutionMode,
    RetryPolicy,
    SyncJobRequest,
    run_candle_sync,
)
from src.candles.repository import SwapCandlesRepository


class _CandleStoreSpy:
    def __init__(self) -> None:
        self.called = False
        self.payload = None

    async def upsert_candles(self, **kwargs):
        self.called = True
        self.payload = kwargs
        return 7

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str) -> int | None:
        return None

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        return {
            "rows_today": 1,
            "funding_rate_non_null": 1,
            "open_interest_non_null": 1,
            "funding_rate_fill_pct": 100.0,
            "open_interest_fill_pct": 100.0,
        }


class _MarketDataStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def fetch_candles(self, **kwargs):
        return [
            {
                "ts": 60_000,
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 10,
            },
        ]

    async def fetch_instruments(self, instrument_type: str = "SWAP"):
        return [{"instId": "BTC-USDT-SWAP"}]

    async def fetch_funding_rates(self, symbols):
        return {s: {} for s in symbols}

    async def fetch_open_interest(self, symbols):
        return {s: {} for s in symbols}


class _InstrumentCatalogStub:
    async def load_curated_symbols(self) -> list[str]:
        return []

    async def refresh_catalog(self) -> list[str]:
        return []

    async def load_cached_symbols(self) -> list[str]:
        return []

    async def list_symbols(self) -> list[str]:
        return ["BTC-USDT-SWAP"]


class _Result:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[object, object]] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, stmt, params=None):
        self.execute_calls.append((stmt, params))
        rowcount = len(params) if isinstance(params, list) else 1
        return _Result(rowcount)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_run_candle_sync_uses_candle_store_port() -> None:
    store = _CandleStoreSpy()
    result = await run_candle_sync(
        SyncJobRequest(
            mode=ExecutionMode.FAST,
            symbols=("BTC-USDT-SWAP",),
            timeframes=("1m",),
            batch_size=10,
            max_retries=1,
            retry_delay=0.1,
            max_concurrent_symbols=1,
        ),
        market_data=_MarketDataStub(),  # type: ignore[arg-type]
        candle_store=store,  # type: ignore[arg-type]
        instrument_catalog=_InstrumentCatalogStub(),  # type: ignore[arg-type]
        retry_policy=RetryPolicy(max_retries=1, retry_delay=0.1, batch_size=10),
    )

    assert result.rows_upserted_total == 7
    assert result.db_write["writes_count"] == 1
    assert store.called is True
    assert store.payload is not None
    assert store.payload["symbol"] == "BTC-USDT-SWAP"
    assert store.payload["timeframe"] == "1m"


@pytest.mark.asyncio
async def test_repository_upsert_candles_uses_aware_utc_fetched_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()

    def _fake_get_db_session() -> _FakeSessionContext:
        return _FakeSessionContext(session)

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)

    saved = await SwapCandlesRepository().upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=[
            {"ts": 60_000, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}
        ],
        additional_data={},
    )

    assert saved == 1
    assert session.committed is True
    _, params = session.execute_calls[-1]
    payload = params[0]
    assert payload["fetched_at"].tzinfo is UTC
