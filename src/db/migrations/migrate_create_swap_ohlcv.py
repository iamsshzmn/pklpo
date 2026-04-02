#!/usr/bin/env python3
"""
Migration to create the swap OHLCV table.
Creates base table for storing swap instrument candles.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

CREATE_SWAP_OHLCV_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS swap_ohlcv_p (
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(30,8) NOT NULL,
    vol_ccy DECIMAL(30,8),
    vol_usd DECIMAL(30,8),
    funding_rate DECIMAL(10,8),
    open_interest DECIMAL(30,8),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, timeframe, timestamp)
);
"""


async def migrate_create_swap_ohlcv() -> None:
    """Create the base swap OHLCV table."""
    logger.info("Creating swap OHLCV table...")

    async with get_db_session() as session:
        try:
            logger.info("Creating main table swap_ohlcv_p...")
            create_table_q = text(CREATE_SWAP_OHLCV_TABLE_SQL)
            await session.execute(create_table_q)
            logger.info("Main table swap_ohlcv_p created")

            logger.info("Creating index...")
            create_index_q = text(
                """
                CREATE INDEX IF NOT EXISTS idx_swap_ohlcv_p_symbol_timeframe_timestamp
                ON swap_ohlcv_p (symbol, timeframe, timestamp);
            """
            )
            await session.execute(create_index_q)
            logger.info("Index created")

            await session.commit()
            logger.info("Swap OHLCV table created successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to create swap OHLCV table: {e}")
            raise
