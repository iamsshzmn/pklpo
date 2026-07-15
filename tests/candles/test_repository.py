from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import exc as sa_exc

from src.candles.repository import SwapCandlesRepository


class _Result:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[Any, Any]] = []
        self.committed = False
        self.rolled_back = False
        self.fail_execute_times = 0

    async def execute(self, stmt: Any, params: Any = None):
        if self.fail_execute_times > 0:
            self.fail_execute_times -= 1
            raise ConnectionRefusedError("db unavailable")
        self.execute_calls.append((stmt, params))
        rowcount = len(params) if isinstance(params, list) else 1
        return _Result(rowcount)

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


@pytest.mark.asyncio
async def test_upsert_candles_uses_bulk_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)

    repo = SwapCandlesRepository()
    candles = [
        {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        {"ts": 2, "open": 2, "high": 3, "low": 1.5, "close": 2.5, "volume": 11},
    ]
    additional = {
        "funding_rate": {"fundingRate": 0.001},
        "open_interest": {"oi": 12345},
    }

    saved = await repo.upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=candles,
        additional_data=additional,
    )

    assert saved == 2
    assert session.committed is True
    assert session.rolled_back is False
    assert len(session.execute_calls) == 1
    _, params = session.execute_calls[0]
    assert isinstance(params, list)
    assert len(params) == 2


class _CountsResult:
    def fetchone(self):
        return (10, 7, 8)


@pytest.mark.asyncio
async def test_get_instrument_counts_uses_single_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()

    async def _execute(stmt: Any, params: Any = None):
        session.execute_calls.append((stmt, params))
        return _CountsResult()

    session.execute = _execute  # type: ignore[assignment]

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)

    repo = SwapCandlesRepository()
    counts = await repo.get_instrument_counts()

    assert counts == {"all": 10, "swap": 7, "usdt": 8}
    assert len(session.execute_calls) == 1


@pytest.mark.asyncio
async def test_upsert_candles_retries_transient_db_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    session.fail_execute_times = 1

    async def _no_sleep(_seconds: float) -> None:
        return None

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)
    monkeypatch.setattr("src.utils.retry.asyncio.sleep", _no_sleep)

    repo = SwapCandlesRepository()
    candles = [
        {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
    ]

    saved = await repo.upsert_candles(
        symbol="BTC-USDT-SWAP",
        timeframe="1m",
        candles=candles,
        additional_data={},
    )

    assert saved == 1
    assert len(session.execute_calls) == 1


class _InvalidatedDBAPIError(sa_exc.DBAPIError):
    """Stub DBAPIError where connection_invalidated is True."""

    def __init__(self) -> None:
        super().__init__(
            statement="SELECT 1",
            params={},
            orig=Exception("connection invalidated"),
            connection_invalidated=True,
        )


@pytest.mark.asyncio
async def test_run_with_db_retry_resets_pool_on_invalidated_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool_reset_calls: list[None] = []

    async def _fake_reset_pool() -> None:
        pool_reset_calls.append(None)

    call_count = 0
    session = _FakeSession()

    async def _execute_raises_first_time(stmt: Any, params: Any = None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _InvalidatedDBAPIError()
        session.execute_calls.append((stmt, params))
        rowcount = len(params) if isinstance(params, list) else 1
        return _Result(rowcount)

    session.execute = _execute_raises_first_time  # type: ignore[assignment]

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)
    monkeypatch.setattr("src.utils.retry.asyncio.sleep", _no_sleep)

    with patch("src.database.reset_pool", new=AsyncMock(side_effect=_fake_reset_pool)):
        repo = SwapCandlesRepository()
        candles = [
            {"ts": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10},
        ]
        saved = await repo.upsert_candles(
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            candles=candles,
            additional_data={},
        )

    assert saved == 1
    assert len(pool_reset_calls) == 1
