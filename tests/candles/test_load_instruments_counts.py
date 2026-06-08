from __future__ import annotations

import pytest

from src.candles.load_instruments import (
    mark_missing_instruments_not_live,
    save_instruments_to_db,
)


class _FakeResult:
    def __init__(self, rows: list[tuple[str]] | None = None, rowcount: int = 0) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows


class _FakeSession:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.execute_results: list[_FakeResult] = []
        self.executed: list[str] = []
        self.committed = False

    async def execute(self, stmt):
        self.execute_calls += 1
        self.executed.append(str(stmt))
        if self.execute_results:
            return self.execute_results.pop(0)
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


class _FakeInsertStmt:
    def __init__(self) -> None:
        self.values_kwargs: dict[str, object] | None = None
        self.on_conflict_kwargs: dict[str, object] | None = None

    def values(self, **kwargs):
        self.values_kwargs = kwargs
        return self

    def on_conflict_do_update(self, **kwargs):
        self.on_conflict_kwargs = kwargs
        return self


class _FakeInsertFactory:
    def __init__(self) -> None:
        self.calls: list[_FakeInsertStmt] = []

    def __call__(self, model):
        del model
        stmt = _FakeInsertStmt()
        self.calls.append(stmt)
        return stmt


@pytest.mark.asyncio
async def test_save_instruments_counts_insert_vs_update(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    session.execute_results = [_FakeResult(rows=[("BTC-USDT-SWAP",)]), _FakeResult()]

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


@pytest.mark.asyncio
async def test_save_instruments_persists_metadata_refreshed_at_ms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    session.execute_results = [_FakeResult(), _FakeResult()]
    fake_insert = _FakeInsertFactory()

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    monkeypatch.setattr("src.candles.load_instruments.get_db_session", _fake_get_db_session)
    monkeypatch.setattr("src.candles.load_instruments.pg_insert", fake_insert)

    instruments = [
        {
            "instId": "BTC-USDT-SWAP",
            "instType": "SWAP",
            "state": "live",
            "listTime": "61000",
        }
    ]

    await save_instruments_to_db(instruments, "SWAP")

    stmt = fake_insert.calls[0]
    assert stmt.values_kwargs is not None
    assert "metadata_refreshed_at_ms" in stmt.values_kwargs
    assert stmt.on_conflict_kwargs is not None
    assert stmt.on_conflict_kwargs["set_"]["metadata_refreshed_at_ms"] is not None


@pytest.mark.asyncio
async def test_mark_missing_instruments_refreshes_metadata_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    session.execute_results = [_FakeResult(rowcount=2)]

    def _fake_get_db_session() -> _FakeSessionCM:
        return _FakeSessionCM(session)

    monkeypatch.setattr("src.candles.load_instruments.get_db_session", _fake_get_db_session)

    updated = await mark_missing_instruments_not_live(
        [{"instId": "BTC-USDT-SWAP"}],
        "SWAP",
    )

    assert updated == 2
    assert session.committed is True
    assert "metadata_refreshed_at_ms" in session.executed[0]
