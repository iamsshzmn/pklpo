"""
Integration/smoke tests for DB reconnect paths in SwapCandlesRepository.

Covers the scenario where Postgres briefly goes down and comes back:
- get_latest_timestamp recovers after transient error
- upsert_candles recovers after transient error
- Persistent outage fails fast with a single clear DatabaseUnavailableError
"""
from __future__ import annotations

from typing import Any

import pytest

from src.candles.application.sync.dto import ExecutionMode, SyncJobRequest
from src.candles.application.sync.policy import RetryPolicy
from src.candles.application.sync.use_cases import (
    DatabaseUnavailableError,
    RunCandleSyncUseCase,
)
from src.candles.repository import SwapCandlesRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeSession:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[Any, Any]] = []
        self.committed = False
        self.rolled_back = False
        self.fail_execute_times = 0

    async def execute(self, stmt: Any, params: Any = None):
        if self.fail_execute_times > 0:
            self.fail_execute_times -= 1
            raise ConnectionRefusedError("simulated db outage")
        self.execute_calls.append((stmt, params))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeSessionCM:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeScalarResult:
    def scalar(self):
        return None


class _LatestTsSession(_FakeSession):
    async def execute(self, stmt: Any, params: Any = None):
        if self.fail_execute_times > 0:
            self.fail_execute_times -= 1
            raise ConnectionRefusedError("simulated db outage")
        self.execute_calls.append((stmt, params))
        return _FakeScalarResult()


# ---------------------------------------------------------------------------
# Repository unit tests — reconnect paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latest_timestamp_recovers_after_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_latest_timestamp must retry and succeed after one transient connection error."""
    session = _LatestTsSession()
    session.fail_execute_times = 1

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)
    monkeypatch.setattr("src.utils.retry.asyncio.sleep", _no_sleep)

    repo = SwapCandlesRepository()
    result = await repo.get_latest_timestamp(symbol="BTC-USDT-SWAP", timeframe="1m")

    assert result is None
    assert len(session.execute_calls) == 1


@pytest.mark.asyncio
async def test_upsert_candles_recovers_after_transient_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """upsert_candles must retry and succeed after one transient connection error."""
    session = _FakeSession()
    session.fail_execute_times = 1

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)
    monkeypatch.setattr("src.utils.retry.asyncio.sleep", _no_sleep)

    repo = SwapCandlesRepository()
    saved = await repo.upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=[{"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}],
        additional_data={},
    )

    assert saved == 1
    assert len(session.execute_calls) == 1


# ---------------------------------------------------------------------------
# Use case level — persistent outage fails with one clear error
# ---------------------------------------------------------------------------

class _MarketDataStub:
    def __init__(self, symbols: list[str]) -> None:
        self._symbols = symbols

    async def __aenter__(self) -> _MarketDataStub:
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def fetch_candles(self, **kwargs):
        return [{"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}]

    async def fetch_instruments(self, instrument_type: str = "SWAP"):
        return [{"instId": s} for s in self._symbols]

    async def fetch_funding_rates(self, instrument_ids: list[str]):
        return {s: {} for s in instrument_ids}

    async def fetch_open_interest(self, instrument_ids: list[str]):
        return {s: {} for s in instrument_ids}


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


class _CandleStorePersistentOutage:
    """Simulates DB that never recovers — all operations raise connection errors."""

    async def upsert_candles(self, **kwargs):
        raise ConnectionRefusedError("db down")

    async def get_latest_timestamp(self, *, symbol: str, timeframe: str) -> int | None:
        raise ConnectionRefusedError("db down")

    async def get_fill_stats(self, start_timestamp_ms: int) -> dict[str, int | float]:
        raise ConnectionRefusedError("db down")


@pytest.mark.asyncio
async def test_persistent_db_outage_raises_database_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When DB is persistently down, the run must fail fast with DatabaseUnavailableError."""
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.candles.application.sync.use_cases.asyncio.sleep", _no_sleep)
    symbols = ["BTC-USDT-SWAP"]
    use_case = RunCandleSyncUseCase(
        market_data=_MarketDataStub(symbols),
        candle_store=_CandleStorePersistentOutage(),
        instrument_catalog=_InstrumentCatalogStub(symbols),
        retry_policy=RetryPolicy(max_retries=0, retry_delay=0.1, batch_size=10),
    )

    with pytest.raises(DatabaseUnavailableError, match="database_unavailable"):
        await use_case.run(SyncJobRequest(mode=ExecutionMode.FAST, max_concurrent_symbols=1))
