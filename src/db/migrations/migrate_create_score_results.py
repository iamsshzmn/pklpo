#!/usr/bin/env python3
"""
Миграция для создания таблицы score_results
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


async def migrate_create_score_results():
    """Создает таблицу score_results"""

    async for session in get_async_session():
        try:
            # Проверяем, существует ли таблица
            check_query = text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = 'score_results'
            """
            )

            result = await session.execute(check_query)
            exists = result.fetchone()

            if not exists:
                # Создаем таблицу
                create_table_query = text(
                    """
                    CREATE TABLE score_results (
                        id BIGSERIAL PRIMARY KEY,
                        symbol VARCHAR NOT NULL,
                        timeframe VARCHAR NOT NULL,
                        ts BIGINT NOT NULL,
                        score_raw NUMERIC(5, 4),
                        score_calibrated NUMERIC(5, 4),
                        p_win NUMERIC(5, 4),
                        edge_net NUMERIC(7, 4),
                        confidence NUMERIC(5, 4),
                        is_valid BOOLEAN DEFAULT TRUE,
                        reasons TEXT[],
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                """
                )

                await session.execute(create_table_query)

                # Создаем индексы
                create_index_query = text(
                    """
                    CREATE INDEX idx_score_results_symbol_timeframe_ts
                    ON score_results(symbol, timeframe, ts)
                """
                )

                await session.execute(create_index_query)

                await session.commit()
                logger.info("✅ Создана таблица score_results с индексами")
            else:
                logger.info("ℹ️ Таблица score_results уже существует")

            logger.info("🎉 Миграция score_results завершена")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_create_score_results())
