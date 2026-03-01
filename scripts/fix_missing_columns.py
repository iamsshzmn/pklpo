#!/usr/bin/env python3
"""
Универсальный скрипт для добавления отсутствующих колонок в таблицу indicators.

Этот скрипт:
1. Анализирует данные, которые пытаются сохраниться
2. Сравнивает их с текущей схемой БД
3. Добавляет отсутствующие колонки автоматически
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Set, List, Dict, Any

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database import create_session
from src.logging_config import setup_logging
import logging

# Настраиваем логирование
setup_logging()
logger = logging.getLogger(__name__)


async def get_current_schema() -> Set[str]:
    """Получает текущую схему таблицы indicators."""

    session = await create_session()
    try:
        try:
            query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                AND table_schema = 'public'
                ORDER BY column_name
            """)

            result = await session.execute(query)
            columns = {row[0] for row in result.fetchall()}

            logger.info(f"📊 Текущая схема indicators: {len(columns)} колонок")
            logger.debug(f"Колонки: {sorted(columns)}")

            return columns

        except Exception as e:
            logger.error(f"❌ Ошибка при получении схемы: {e}")
            return set()
        finally:
            await session.close()


async def get_sample_data_columns() -> Set[str]:
    """Получает колонки из последних данных в таблице indicators."""

    session = await create_session()
    try:
        try:
            # Получаем последние записи для анализа структуры данных
            query = text("""
                SELECT * FROM indicators
                ORDER BY calculated_at DESC
                LIMIT 1
            """)

            result = await session.execute(query)
            row = result.fetchone()

            if row:
                # Получаем имена колонок из результата
                columns = set(row._mapping.keys())
                logger.info(f"📊 Колонки в последней записи: {len(columns)}")
                logger.debug(f"Колонки: {sorted(columns)}")
                return columns
            else:
                logger.warning("⚠️ Нет данных в таблице indicators для анализа")
                return set()

        except Exception as e:
            logger.error(f"❌ Ошибка при анализе данных: {e}")
            return set()
        finally:
            await session.close()


async def add_missing_columns(missing_columns: List[str]) -> bool:
    """Добавляет отсутствующие колонки в таблицу indicators."""

    if not missing_columns:
        logger.info("✅ Отсутствующих колонок не найдено")
        return True

    session = await create_session()
    try:
        try:
            logger.info(f"➕ Добавляем {len(missing_columns)} отсутствующих колонок...")

            for column in missing_columns:
                logger.info(f"   - Добавляем колонку: {column}")

                # Определяем тип данных для колонки
                # По умолчанию используем DECIMAL(20,8) для числовых полей
                add_query = text(f"""
                    ALTER TABLE indicators
                    ADD COLUMN {column} DECIMAL(20,8)
                """)

                await session.execute(add_query)
                logger.info(f"   ✅ Колонка {column} добавлена")

            await session.commit()
            logger.info("✅ Все отсутствующие колонки добавлены успешно")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении колонок: {e}")
            await session.rollback()
            return False
        finally:
            await session.close()


async def analyze_and_fix_schema():
    """Анализирует схему и добавляет отсутствующие колонки."""

    logger.info("🔍 Анализируем схему таблицы indicators...")

    # Получаем текущую схему
    current_schema = await get_current_schema()
    if not current_schema:
        logger.error("❌ Не удалось получить схему таблицы")
        return False

    # Получаем колонки из данных
    data_columns = await get_sample_data_columns()
    if not data_columns:
        logger.warning("⚠️ Не удалось проанализировать данные")
        return False

    # Находим отсутствующие колонки
    missing_columns = sorted(data_columns - current_schema)

    if missing_columns:
        logger.warning(f"⚠️ Найдено {len(missing_columns)} отсутствующих колонок:")
        for col in missing_columns:
            logger.warning(f"   - {col}")

        # Добавляем отсутствующие колонки
        success = await add_missing_columns(missing_columns)
        return success
    else:
        logger.info("✅ Все колонки присутствуют в схеме")
        return True


async def main():
    """Основная функция скрипта."""

    logger.info("🚀 Запуск скрипта исправления схемы таблицы indicators")
    logger.info("=" * 70)

    success = await analyze_and_fix_schema()

    if success:
        logger.info("🎉 Скрипт выполнен успешно!")
        logger.info("💡 Теперь можно перезапустить DAG features_calc")
    else:
        logger.error("💥 Скрипт завершился с ошибкой")
        sys.exit(1)

    logger.info("=" * 70)
    logger.info("🏁 Скрипт завершён")


if __name__ == "__main__":
    asyncio.run(main())
