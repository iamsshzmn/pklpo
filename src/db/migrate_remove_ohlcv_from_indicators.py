#!/usr/bin/env python3
"""
Миграция для удаления OHLCV колонок из таблицы indicators.

OHLCV данные уже есть в таблице swap_ohlcv_p, поэтому дублирование
в таблице indicators избыточно и увеличивает размер базы данных.
"""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_remove_ohlcv_from_indicators() -> None:
    """
    Удаляет OHLCV колонки из таблицы indicators.
    """
    logger.info("🗑️ Удаляем OHLCV колонки из таблицы indicators...")

    async with get_db_session() as session:
        try:
            # Проверяем, существуют ли колонки
            result = await session.execute(
                text(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                AND column_name IN ('open', 'high', 'low', 'close', 'volume')
                ORDER BY column_name;
            """
                )
            )

            existing_columns = [row[0] for row in result.fetchall()]

            if not existing_columns:
                logger.info("✅ OHLCV колонки уже отсутствуют в таблице indicators")
                return

            logger.info(f"📋 Найдены OHLCV колонки: {existing_columns}")

            # Удаляем каждую колонку
            for column in existing_columns:
                logger.info(f"🗑️ Удаляем колонку {column}...")
                await session.execute(
                    text(f"ALTER TABLE indicators DROP COLUMN IF EXISTS {column};")
                )
                await session.commit()
                logger.info(f"✅ Колонка {column} удалена")

            # Создаем VIEW для удобства работы с данными
            logger.info("🔄 Создаем VIEW indicators_with_ohlcv...")

            await session.execute(
                text(
                    """
                CREATE OR REPLACE VIEW indicators_with_ohlcv AS
                SELECT
                    i.*,
                    o.open,
                    o.high,
                    o.low,
                    o.close,
                    o.volume
                FROM indicators i
                LEFT JOIN swap_ohlcv_p o ON (
                    i.symbol = o.symbol
                    AND i.timeframe = o.timeframe
                    AND i.timestamp = o.timestamp
                );
            """
                )
            )
            await session.commit()
            logger.info("✅ VIEW indicators_with_ohlcv создан")

            # Создаем индекс для оптимизации JOIN'ов
            logger.info("🔄 Создаем индекс для оптимизации JOIN'ов...")

            await session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_swap_ohlcv_p_lookup
                ON swap_ohlcv_p (symbol, timeframe, timestamp);
            """
                )
            )
            await session.commit()
            logger.info("✅ Индекс для JOIN'ов создан")

            logger.info("✅ Миграция удаления OHLCV колонок завершена успешно!")

        except Exception as e:
            logger.error(f"❌ Ошибка при удалении OHLCV колонок: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(migrate_remove_ohlcv_from_indicators())
