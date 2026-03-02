"""Deprecated compatibility wrapper for legacy candles sync entrypoint."""

from __future__ import annotations

import asyncio
import warnings
from typing import Any

from src.candles.sync_swap_candles import SWAP_BARS, sync_swap_candles

BARS = SWAP_BARS


def _normalize_legacy_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value:
        return value
    if value.endswith("-SWAP"):
        return value
    if value.count("-") == 1:
        return f"{value}-SWAP"
    return value


async def fetch_and_sync_candles(
    symbol: str | None = None,
    *,
    timeframes: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Backward-compatible wrapper over ``sync_swap_candles``.

    Legacy callers should migrate to ``src.candles.sync_swap_candles.sync_swap_candles``.
    """
    warnings.warn(
        (
            "src.candles.sync_candles.fetch_and_sync_candles is deprecated and will be "
            "removed in v2.0. Use src.candles.sync_swap_candles.sync_swap_candles."
        ),
        DeprecationWarning,
        stacklevel=2,
    )
    normalized = _normalize_legacy_symbol(symbol) if symbol else None
    symbols = [normalized] if normalized else None
    return await sync_swap_candles(symbols=symbols, timeframes=timeframes, config=config)


if __name__ == "__main__":
    asyncio.run(fetch_and_sync_candles())
