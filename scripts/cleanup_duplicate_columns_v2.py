#!/usr/bin/env python3
"""
Скрипт для очистки дубликатов колонок в таблице indicators.
Удаляет старые версии без подчёркивания и оставляет только нормализованные.
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

# Маппинг старых имён на новые
COLUMN_MAPPING = {
    "ema12": "ema_12",
    "ema21": "ema_21",
    "ema26": "ema_26",
    "ema50": "ema_50",
    "ema200": "ema_200",
    "sma200": "sma_200",
    "sma34": "sma_34",
    "sma50": "sma_50",
    "cci_14": "cci_14",  # Уже правильное
    "mfi_14": "mfi_14",  # Уже правильное
}


async def cleanup_duplicate_columns():
    """Очищаем дубликаты колонок в таблице indicators"""

    session = await create_session()

    try:
        # 1. Удаляем зависимые view
        logger.info("Удаляем зависимые view...")
        try:
            await session.execute(
                text("DROP VIEW IF EXISTS indicators_reordered CASCADE")
            )
            logger.info("✅ View indicators_reordered удалён")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при удалении view: {e}")

        # 2. Получаем текущую схему
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
        current_columns = {row[0] for row in result.fetchall()}

        logger.info(f"Текущие колонки: {len(current_columns)}")

        # 3. Находим дубликаты
        duplicates_to_remove = []
        for old_name, new_name in COLUMN_MAPPING.items():
            if old_name in current_columns and new_name in current_columns:
                duplicates_to_remove.append(old_name)
                logger.info(f"Найден дубликат: {old_name} -> {new_name}")

        if not duplicates_to_remove:
            logger.info("Дубликаты не найдены")
            return

        # 4. Удаляем старые колонки
        for old_column in duplicates_to_remove:
            try:
                await session.execute(
                    text(f"ALTER TABLE indicators DROP COLUMN IF EXISTS {old_column}")
                )
                logger.info(f"✅ Удалена колонка: {old_column}")
            except Exception as e:
                logger.error(f"❌ Ошибка при удалении {old_column}: {e}")

        await session.commit()
        logger.info("✅ Очистка дубликатов завершена")

        # 5. Проверяем результат
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
        new_columns = {row[0] for row in result.fetchall()}

        logger.info(f"Колонок после очистки: {len(new_columns)}")
        logger.info(f"Удалено дубликатов: {len(duplicates_to_remove)}")

    except Exception as e:
        logger.error(f"Ошибка при очистке дубликатов: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()


async def main():
    """Основная функция"""
    logger.info("🧹 Начинаем очистку дубликатов колонок...")
    await cleanup_duplicate_columns()
    logger.info("✅ Очистка завершена")


if __name__ == "__main__":
    asyncio.run(main())
