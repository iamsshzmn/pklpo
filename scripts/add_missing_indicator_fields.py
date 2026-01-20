#!/usr/bin/env python3
"""
Скрипт для добавления недостающих полей в модель Indicator
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text

from src.database import create_session

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_missing_fields():
    """Добавляем недостающие поля в таблицу indicators"""

    # Поля, которые нужно добавить
    missing_fields = [
        "midpoint",
        "midprice",
        "wcp",
        "hwma_20",
        "ttm_trend",
        "decay",
        "long_run",
        "decreasing",
        "increasing",
        "amat",
        "short_run",
    ]

    session = await create_session()

    try:
        # Проверяем существующие колонки
        result = await session.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND table_schema = 'public'
        """
            )
        )
        existing_columns = {row[0] for row in result.fetchall()}

        logger.info(f"Существующие колонки: {len(existing_columns)}")

        # Добавляем недостающие поля
        for field in missing_fields:
            if field not in existing_columns:
                logger.info(f"Добавляем колонку: {field}")
                await session.execute(
                    text(
                        f"""
                    ALTER TABLE indicators
                    ADD COLUMN {field} DECIMAL(20,8)
                """
                    )
                )
            else:
                logger.info(f"Колонка {field} уже существует")

        await session.commit()
        logger.info("✅ Все недостающие поля добавлены успешно!")

        # Проверяем результат
        result = await session.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND table_schema = 'public'
            ORDER BY column_name
        """
            )
        )
        final_columns = {row[0] for row in result.fetchall()}

        logger.info(f"Итого колонок: {len(final_columns)}")
        logger.info(f"Добавленные поля: {sorted(missing_fields)}")

    except Exception as e:
        logger.error(f"Ошибка при добавлении полей: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()


async def main():
    """Основная функция"""
    logger.info("🚀 Начинаем добавление недостающих полей в таблицу indicators")

    try:
        await add_missing_fields()
        logger.info("✅ Миграция завершена успешно!")
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
