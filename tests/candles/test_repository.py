from __future__ import annotations

from typing import Any

import pytest

from src.candles.repository import SwapCandlesRepository


class _FakeSession:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[Any, Any]] = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, stmt: Any, params: Any = None):
        self.execute_calls.append((stmt, params))
        return None

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
async def test_upsert_swap_candles_uses_bulk_execute(monkeypatch: pytest.MonkeyPatch) -> None:
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

    saved = await repo.upsert_swap_candles(
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
async def test_fetch_instrument_counts_uses_single_query(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()

    async def _execute(stmt: Any, params: Any = None):
        session.execute_calls.append((stmt, params))
        return _CountsResult()

    session.execute = _execute  # type: ignore[assignment]

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    monkeypatch.setattr("src.candles.repository.get_db_session", _fake_get_db_session)

    repo = SwapCandlesRepository()
    counts = await repo.fetch_instrument_counts()

    assert counts == {"all": 10, "swap": 7, "usdt": 8}
    assert len(session.execute_calls) == 1
