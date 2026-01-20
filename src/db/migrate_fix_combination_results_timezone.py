#!/usr/bin/env python3
"""
Миграция для исправления timezone в таблице combination_results
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

import asyncio

from sqlalchemy import text

from src.database import get_async_session


async def migrate_fix_timezone():
    """Исправляет timezone в таблице combination_results"""
    async for session in get_async_session():
        try:
            print("🔧 Исправление timezone в таблице combination_results...")

            # Изменяем тип колонки calculated_at на TIMESTAMP WITH TIME ZONE
            alter_query = text(
                """
                ALTER TABLE combination_results
                ALTER COLUMN calculated_at TYPE TIMESTAMP WITH TIME ZONE
                USING calculated_at AT TIME ZONE 'UTC'
            """
            )

            await session.execute(alter_query)
            await session.commit()

            print("✅ Timezone исправлен в таблице combination_results")

        except Exception as e:
            print(f"❌ Ошибка при миграции: {e}")
            await session.rollback()


if __name__ == "__main__":
    asyncio.run(migrate_fix_timezone())
