from __future__ import annotations

from typing import Any

from src.candles.domain.sync_config import DEFAULT_CONFIG, SWAP_BARS
from src.candles.sync_runtime import run_sync_via_application


async def sync_swap_candles(
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_config = {**DEFAULT_CONFIG, **(config or {})}
    return await run_sync_via_application(
        symbols=symbols,
        timeframes=timeframes,
        config=effective_config,
        default_timeframes=SWAP_BARS,
    )


__all__ = ["sync_swap_candles"]

