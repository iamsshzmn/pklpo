#!/usr/bin/env python3
"""
Скрипт для добавления отсутствующей колонки ics_26 в таблицу indicators.

Проблема: В логах видно ошибку 'Database insertion failed: 'ics_26'',
что означает, что поле ics_26 присутствует в данных, но отсутствует в схеме БД.

Решение: Добавляем колонку ics_26 в таблицу indicators.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

from sqlalchemy import text

from src.database import create_session
from src.logging_config import setup_logging

# Настраиваем логирование
setup_logging()
logger = logging.getLogger(__name__)


async def add_ics_26_column():
    """Добавляет колонку ics_26 в таблицу indicators."""

    session = await create_session()
    try:
        # Проверяем, существует ли уже колонка ics_26
        logger.info("🔍 Проверяем существование колонки ics_26...")

        check_query = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND column_name = 'ics_26'
            AND table_schema = 'public'
        """
        )

        result = await session.execute(check_query)
        existing_column = result.fetchone()

        if existing_column:
            logger.info("✅ Колонка ics_26 уже существует в таблице indicators")
            return True

        # Добавляем колонку ics_26
        logger.info("➕ Добавляем колонку ics_26 в таблицу indicators...")

        add_column_query = text(
            """
            ALTER TABLE indicators
            ADD COLUMN ics_26 DECIMAL(20,8)
        """
        )

        await session.execute(add_column_query)
        await session.commit()

        logger.info("✅ Колонка ics_26 успешно добавлена в таблицу indicators")

        # Проверяем, что колонка действительно добавлена
        verify_query = text(
            """
            SELECT column_name, data_type, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND column_name = 'ics_26'
            AND table_schema = 'public'
        """
        )

        result = await session.execute(verify_query)
        column_info = result.fetchone()

        if column_info:
            logger.info(
                f"✅ Подтверждено: колонка {column_info[0]} типа {column_info[1]} добавлена"
            )
            return True
        logger.error("❌ Колонка ics_26 не найдена после добавления")
        return False

    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении колонки ics_26: {e}")
        await session.rollback()
        return False
    finally:
        await session.close()


async def check_table_schema():
    """Проверяет текущую схему таблицы indicators."""

    session = await create_session()
    try:
        logger.info("🔍 Проверяем схему таблицы indicators...")

        schema_query = text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """
        )

        result = await session.execute(schema_query)
        columns = result.fetchall()

        logger.info(f"📊 Таблица indicators содержит {len(columns)} колонок:")
        for col in columns:
            logger.info(
                f"   - {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})"
            )

        # Проверяем наличие ics_26
        ics_26_exists = any(col[0] == "ics_26" for col in columns)
        if ics_26_exists:
            logger.info("✅ Колонка ics_26 присутствует в схеме")
        else:
            logger.warning("⚠️ Колонка ics_26 отсутствует в схеме")

        return ics_26_exists

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке схемы: {e}")
        return False
    finally:
        await session.close()


async def main():
    """Основная функция скрипта."""

    logger.info("🚀 Запуск скрипта добавления колонки ics_26")
    logger.info("=" * 60)

    # Проверяем текущую схему
    logger.info("📋 Шаг 1: Проверка текущей схемы таблицы")
    schema_ok = await check_table_schema()

    if not schema_ok:
        logger.info("📋 Шаг 2: Добавление колонки ics_26")
        success = await add_ics_26_column()

        if success:
            logger.info("📋 Шаг 3: Финальная проверка схемы")
            await check_table_schema()
            logger.info("🎉 Скрипт выполнен успешно!")
        else:
            logger.error("💥 Скрипт завершился с ошибкой")
            sys.exit(1)
    else:
        logger.info(
            "✅ Колонка ics_26 уже существует, дополнительных действий не требуется"
        )

    logger.info("=" * 60)
    logger.info("🏁 Скрипт завершён")


if __name__ == "__main__":
    asyncio.run(main())
