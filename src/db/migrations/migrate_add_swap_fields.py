"""
Миграция для добавления полей свопов в таблицу instruments
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


async def run_migrations():
    """Выполняет миграции для добавления полей свопов"""
    logger.info("🔄 Начинаем миграцию для добавления полей свопов...")

    async for session in get_async_session():
        try:
            # Проверяем существование колонок перед добавлением
            check_columns_query = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'instruments'
                AND column_name IN ('contract_val', 'settle_ccy', 'ct_type', 'minSz', 'maxSz', 'minNotional')
            """
            )

            result = await session.execute(check_columns_query)
            existing_columns = {row[0] for row in result.fetchall()}
            logger.info(f"Существующие колонки: {existing_columns}")

            # Добавляем новые колонки для свопов
            columns_to_add = [
                ("contract_val", "FLOAT"),
                ("settle_ccy", "VARCHAR"),
                ("ct_type", "VARCHAR"),
                ("minSz", "FLOAT"),
                ("maxSz", "FLOAT"),
                ("minNotional", "FLOAT"),
            ]

            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    try:
                        add_column_query = text(
                            f'ALTER TABLE instruments ADD COLUMN "{column_name}" {column_type}'
                        )
                        await session.execute(add_column_query)
                        logger.info(f"✅ Добавлена колонка {column_name}")
                    except Exception as e:
                        logger.error(
                            f"❌ Ошибка при добавлении колонки {column_name}: {e}"
                        )
                else:
                    logger.info(f"ℹ️ Колонка {column_name} уже существует")

            await session.commit()
            logger.info("🎉 Миграция для полей свопов завершена успешно!")

        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении миграции: {e}")
            await session.rollback()
            raise
        finally:
            break


if __name__ == "__main__":
    asyncio.run(run_migrations())
