from __future__ import annotations

from typing import Any

import pytest


class _Session:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> None:
        self.calls.append((str(statement), params or {}))


@pytest.mark.asyncio
async def test_symbol_writer_lock_takes_shared_global_then_pair_exclusive() -> None:
    from src.candles.infrastructure.ohlcv_write_lock import ohlcv_symbol_write_lock

    session = _Session()

    async with ohlcv_symbol_write_lock(
        session,
        symbol="BTC-USDT-SWAP",
        timeframe="1H",
    ):
        pass

    assert "pg_advisory_xact_lock_shared" in session.calls[0][0]
    assert session.calls[0][1]["lock_key"] > 0
    assert "pg_advisory_xact_lock" in session.calls[1][0]
    assert session.calls[1][1]["lock_scope"] == "swap_ohlcv_p"
    assert session.calls[1][1]["lock_key"] == "BTC-USDT-SWAP:1H"


@pytest.mark.asyncio
async def test_retention_lock_takes_global_exclusive() -> None:
    from src.candles.infrastructure.ohlcv_write_lock import ohlcv_retention_write_lock

    session = _Session()

    async with ohlcv_retention_write_lock(session):
        pass

    assert len(session.calls) == 1
    assert "pg_advisory_xact_lock(" in session.calls[0][0]
    assert "pg_advisory_xact_lock_shared" not in session.calls[0][0]
    assert session.calls[0][1]["lock_key"] > 0
