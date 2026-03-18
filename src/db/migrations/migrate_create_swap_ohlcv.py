#!/usr/bin/env python3
"""
Упрощенная миграция для создания таблицы swap OHLCV.
Создает базовую таблицу для хранения свечей swap инструментов.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_create_swap_ohlcv() -> None:
    """
    Создает базовую таблицу swap OHLCV.
    """
    logger.info("📊 Создаем упрощенную таблицу swap OHLCV...")

    async with get_db_session() as session:
        try:
            # Создаем основную таблицу swap_ohlcv_p
            logger.info("🔄 Создаем основную таблицу swap_ohlcv_p...")
            create_table_q = text(
                """
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
                    fetched_at TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (symbol, timeframe, timestamp)
                );
            """
            )
            await session.execute(create_table_q)
            logger.info("✅ Основная таблица swap_ohlcv_p создана")

            # Создаем простой индекс
            logger.info("🔄 Создаем простой индекс...")
            create_index_q = text(
                """
                CREATE INDEX IF NOT EXISTS idx_swap_ohlcv_p_symbol_timeframe_timestamp
                ON swap_ohlcv_p (symbol, timeframe, timestamp);
            """
            )
            await session.execute(create_index_q)
            logger.info("✅ Индекс создан")

            await session.commit()
            logger.info("🎉 Таблица swap OHLCV создана успешно!")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка при создании таблицы swap OHLCV: {e}")
            raise
