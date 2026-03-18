#!/usr/bin/env python3
"""
Миграция для добавления недостающих колонок в таблицу indicators.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Переопределяем DATABASE_URL для подключения с хоста
DATABASE_URL = "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo"

engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logger = logging.getLogger(__name__)


async def migrate_add_missing_columns() -> None:
    """Добавляет недостающие колонки в таблицу indicators."""

    async with async_session() as session:
        try:
            # Список недостающих колонок из лога ошибок
            missing_columns = [
                ("pvi", "DECIMAL(10,4)"),
                ("ad", "DECIMAL(10,4)"),
                ("rsx_14", "DECIMAL(10,4)"),
                ("trange", "DECIMAL(10,4)"),
                ("nvi", "DECIMAL(10,4)"),
                ("bop", "DECIMAL(10,4)"),
                ("rsx", "DECIMAL(10,4)"),
            ]

            for column_name, column_type in missing_columns:
                # Проверяем, существует ли колонка
                check_query = text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'indicators'
                    AND column_name = :column_name
                    AND table_schema = 'public'
                """
                )

                result = await session.execute(
                    check_query, {"column_name": column_name}
                )
                exists = result.fetchone() is not None

                if not exists:
                    # Добавляем колонку
                    add_column_query = text(
                        f"""
                        ALTER TABLE indicators
                        ADD COLUMN {column_name} {column_type}
                    """
                    )

                    await session.execute(add_column_query)
                    logger.info(f"✅ Added column {column_name} to indicators table")
                else:
                    logger.info(f"⏭️ Column {column_name} already exists")

            await session.commit()
            logger.info("🎉 Migration completed successfully")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(migrate_add_missing_columns())
