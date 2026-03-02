#!/usr/bin/env python3
"""
Auto-refresh instruments_list.json for candle sync.
Keeps BTC and ETH first, appends the rest in alphabetical order.
"""

import asyncio

from src.candles.instruments_service import refresh_instruments_list
from src.candles.repository import SwapCandlesRepository
from src.logging import get_logger, setup_logging

logger = get_logger("candles.update_instruments_list")


async def update_instruments_list() -> None:
    """
    Refresh instruments_list.json from DB.
    Uses the shared instruments service to keep runtime and helper behavior aligned.
    """
    repository = SwapCandlesRepository()
    await refresh_instruments_list(repository=repository, logger=logger)


async def main():
    """Main entrypoint for running the update manually."""
    setup_logging(level="INFO")

    logger.info("Starting instruments list auto-refresh")
    await update_instruments_list()
    logger.info("Instruments list auto-refresh finished")


if __name__ == "__main__":
    asyncio.run(main())
