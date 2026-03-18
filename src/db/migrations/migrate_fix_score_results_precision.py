"""
Миграция для исправления точности полей в таблице score_results.
Увеличивает точность полей для корректного сохранения больших значений scores.
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import get_async_session

logger = logging.getLogger(__name__)


async def migrate_fix_score_results_precision():
    """Исправляет точность полей в таблице score_results"""
    logger.info("🔧 Миграция: Исправление точности полей в таблице score_results")
    logger.info("=" * 80)

    async for session in get_async_session():
        try:
            # Проверяем текущую структуру таблицы
            check_query = text(
                """
                SELECT column_name, data_type, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_name = 'score_results'
                AND column_name IN ('score_raw', 'score_calibrated', 'p_win', 'edge_net', 'confidence')
                ORDER BY column_name
            """
            )

            result = await session.execute(check_query)
            current_columns = result.fetchall()

            logger.info("📋 Текущая структура полей:")
            for col in current_columns:
                logger.info(
                    f"   {col.column_name}: {col.data_type}({col.numeric_precision},{col.numeric_scale})"
                )

            # Изменяем точность полей
            alter_queries = [
                "ALTER TABLE score_results ALTER COLUMN score_raw TYPE NUMERIC(10, 6)",
                "ALTER TABLE score_results ALTER COLUMN score_calibrated TYPE NUMERIC(10, 6)",
                "ALTER TABLE score_results ALTER COLUMN p_win TYPE NUMERIC(10, 6)",
                "ALTER TABLE score_results ALTER COLUMN edge_net TYPE NUMERIC(12, 6)",
                "ALTER TABLE score_results ALTER COLUMN confidence TYPE NUMERIC(10, 6)",
            ]

            for query in alter_queries:
                logger.info(f"🔄 Выполняем: {query}")
                await session.execute(text(query))

            await session.commit()

            # Проверяем новую структуру
            result = await session.execute(check_query)
            new_columns = result.fetchall()

            logger.info("📋 Новая структура полей:")
            for col in new_columns:
                logger.info(
                    f"   {col.column_name}: {col.data_type}({col.numeric_precision},{col.numeric_scale})"
                )

            logger.info("✅ Миграция завершена успешно!")
            break

        except Exception as e:
            logger.error(f"❌ Ошибка при миграции: {e}")
            await session.rollback()
            break


async def run_migrations():
    """Запускает миграции"""
    await migrate_fix_score_results_precision()


if __name__ == "__main__":
    asyncio.run(run_migrations())
