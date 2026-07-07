from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest

from src.candles.repository import SwapCandlesRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class _Session:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(
        self,
        statement: Any,
        params: dict[str, Any] | None = None,
    ) -> _Result:
        self.calls.append((str(statement), params or {}))
        return _Result(self.rows)


def _patch_session(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[tuple[Any, ...]],
) -> _Session:
    session = _Session(rows)

    @asynccontextmanager
    async def _session_factory() -> AsyncIterator[_Session]:
        yield session

    monkeypatch.setattr(
        "src.candles.repository.get_db_session",
        _session_factory,
    )
    return session


@pytest.mark.asyncio
async def test_get_instrument_states_returns_only_present_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _patch_session(
        monkeypatch,
        [("BTC-USDT-SWAP", "live"), ("TON-USDT-SWAP", "expired")],
    )
    repo = SwapCandlesRepository()

    states = await repo.get_instrument_states(
        ["BTC-USDT-SWAP", "MISSING-USDT-SWAP", "TON-USDT-SWAP"]
    )

    assert states == {"BTC-USDT-SWAP": "live", "TON-USDT-SWAP": "expired"}
    query, params = session.calls[0]
    assert "FROM instruments" in query
    assert "symbol = ANY(:symbols)" in query
    assert params == {
        "symbols": ["BTC-USDT-SWAP", "MISSING-USDT-SWAP", "TON-USDT-SWAP"]
    }


@pytest.mark.asyncio
async def test_get_instrument_states_empty_symbols_skips_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _patch_session(monkeypatch, [])
    repo = SwapCandlesRepository()

    states = await repo.get_instrument_states([])

    assert states == {}
    assert session.calls == []
