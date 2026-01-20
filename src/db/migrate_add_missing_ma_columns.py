#!/usr/bin/env python3
"""
Миграция для добавления недостающих MA колонок в таблицу indicators
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


async def migrate_add_missing_ma_columns():
    """Добавляет недостающие MA колонки в таблицу indicators"""

    async for session in get_async_session():
        try:
            # Список колонок для добавления
            columns_to_add = [
                ("ema12", "NUMERIC"),
                ("ema26", "NUMERIC"),
                ("ema50", "NUMERIC"),
                ("sma34", "NUMERIC"),
            ]

            for column_name, column_type in columns_to_add:
                try:
                    # Проверяем, существует ли колонка
                    check_query = text(
                        f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'indicators'
                        AND column_name = '{column_name}'
                    """
                    )

                    result = await session.execute(check_query)
                    exists = result.fetchone()

                    if not exists:
                        # Добавляем колонку
                        add_column_query = text(
                            f"""
                            ALTER TABLE indicators
                            ADD COLUMN {column_name} {column_type}
                        """
                        )

                        await session.execute(add_column_query)
                        await session.commit()
                        logger.info(f"✅ Добавлена колонка {column_name}")
                    else:
                        logger.info(f"ℹ️ Колонка {column_name} уже существует")

                except Exception as e:
                    logger.error(f"❌ Ошибка при добавлении колонки {column_name}: {e}")
                    await session.rollback()
                    continue

            logger.info("🎉 Миграция MA колонок завершена")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_add_missing_ma_columns())
