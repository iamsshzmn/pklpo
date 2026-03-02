#!/usr/bin/env python3
"""
Миграция для создания таблицы combination_results
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import get_async_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_create_combination_results():
    """Создает таблицу combination_results"""

    async for session in get_async_session():
        try:
            # Проверяем, существует ли таблица
            check_query = text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'combination_results'
            """
            )

            result = await session.execute(check_query)
            exists = result.fetchone()

            if not exists:
                # Создаем таблицу
                create_table_query = text(
                    """
                    CREATE TABLE combination_results (
                        symbol VARCHAR NOT NULL,
                        timeframe VARCHAR NOT NULL,
                        ts BIGINT NOT NULL,
                        combination_name VARCHAR NOT NULL,
                        signal_strength NUMERIC,
                        agreement_count SMALLINT,
                        conflict_count SMALLINT,
                        recommendation VARCHAR,
                        trading_action VARCHAR,
                        risk_assessment VARCHAR,
                        timeframe_advice VARCHAR,
                        confidence_level VARCHAR,
                        indicators_used VARCHAR,
                        calculated_at TIMESTAMP,
                        PRIMARY KEY (symbol, timeframe, ts, combination_name)
                    )
                """
                )

                await session.execute(create_table_query)
                await session.commit()
                logger.info("✅ Создана таблица combination_results")
            else:
                logger.info("ℹ️ Таблица combination_results уже существует")

            logger.info("🎉 Миграция combination_results завершена")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_create_combination_results())
