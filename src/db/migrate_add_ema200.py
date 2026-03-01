#!/usr/bin/env python3
"""
Миграция для добавления ema200 в таблицу indicators
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


async def migrate_add_ema200():
    """Добавляет ema200 в таблицу indicators"""

    async for session in get_async_session():
        try:
            # Проверяем, существует ли колонка
            check_query = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                AND column_name = 'ema200'
            """
            )

            result = await session.execute(check_query)
            exists = result.fetchone()

            if not exists:
                # Добавляем колонку
                add_column_query = text(
                    """
                    ALTER TABLE indicators
                    ADD COLUMN ema200 NUMERIC
                """
                )

                await session.execute(add_column_query)
                await session.commit()
                logger.info("✅ Добавлена колонка ema200")
            else:
                logger.info("ℹ️ Колонка ema200 уже существует")

            logger.info("🎉 Миграция ema200 завершена")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_add_ema200())
