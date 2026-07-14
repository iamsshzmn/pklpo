from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from sqlalchemy import text

OHLCV_GLOBAL_WRITE_LOCK_KEY = 7_417_042_793_376_083
OHLCV_LOCK_SCOPE = "swap_ohlcv_p"


@asynccontextmanager
async def ohlcv_symbol_write_lock(
    session: Any,
    *,
    symbol: str,
    timeframe: str,
) -> AsyncIterator[None]:
    """Serialize writes for one pair while allowing retention to block all writers."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock_shared(:lock_key)"),
        {"lock_key": OHLCV_GLOBAL_WRITE_LOCK_KEY},
    )
    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock(hashtext(:lock_scope), hashtext(:lock_key))"
        ),
        {"lock_scope": OHLCV_LOCK_SCOPE, "lock_key": f"{symbol}:{timeframe}"},
    )
    yield


@asynccontextmanager
async def ohlcv_retention_write_lock(session: Any) -> AsyncIterator[None]:
    """Take the global exclusive OHLCV write lock for retention cleanup."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": OHLCV_GLOBAL_WRITE_LOCK_KEY},
    )
    yield
