#!/usr/bin/env python3
"""
Auto-refresh instruments_list.json for candle sync.
Keeps BTC and ETH first, appends the rest in alphabetical order.
"""

import asyncio

from src.logging import get_logger, setup_logging

logger = get_logger("candles.update_instruments_list")


async def update_instruments_list() -> None:
    """
    Keep instruments_list.json fixed and skip any automatic refresh.
    """
    logger.info("Instrument list is fixed; automatic update is disabled")


async def main():
    """Main entrypoint for running the update manually."""
    setup_logging(level="INFO")

    logger.info("Starting instruments list auto-refresh")
    await update_instruments_list()
    logger.info("Instruments list auto-refresh finished")


if __name__ == "__main__":
    asyncio.run(main())
