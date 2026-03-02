from __future__ import annotations

import pytest

from src.candles.load_instruments import save_instruments_to_db


class _FakeResult:
    def __init__(self, rows: list[tuple[str]] | None = None) -> None:
        self._rows = rows or []

    def fetchall(self):
        return self._rows


class _FakeSession:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.committed = False

    async def execute(self, stmt):
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _FakeResult(rows=[("BTC-USDT-SWAP",)])
        return _FakeResult()

    async def commit(self) -> None:
        self.committed = True


class _FakeSessionCM:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_save_instruments_counts_insert_vs_update(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    monkeypatch.setattr("src.candles.load_instruments.get_db_session", _fake_get_db_session)

    instruments = [
        {"instId": "BTC-USDT-SWAP", "instType": "SWAP", "state": "live"},
        {"instId": "ETH-USDT-SWAP", "instType": "SWAP", "state": "live"},
    ]

    inserted, updated = await save_instruments_to_db(instruments, "SWAP")

    assert inserted == 1
    assert updated == 1
    assert session.committed is True
