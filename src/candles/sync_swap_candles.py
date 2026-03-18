#!/usr/bin/env python3
"""Thin compatibility shim for swap candle synchronization."""

from __future__ import annotations

import asyncio

from src.candles.domain.sync_config import DEFAULT_CONFIG, SWAP_BARS
from src.candles.interfaces.swap_sync import sync_swap_candles
from src.logging import get_logger, setup_logging

logger = get_logger("candles.sync_swap_candles")

__all__ = [
    "DEFAULT_CONFIG",
    "SWAP_BARS",
    "sync_swap_candles",
]


if __name__ == "__main__":
    setup_logging(level="INFO")
    logger.info("Launching swap candles sync module")
    asyncio.run(sync_swap_candles())
