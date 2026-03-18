import asyncio
import os
import sys

from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database import get_async_session


async def migrate_add_ohlcv_columns():
    """Добавляет OHLCV колонки в таблицу indicators"""
    async for session in get_async_session():
        try:
            # Проверяем, существуют ли уже колонки
            check_query = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                AND column_name IN ('open', 'high', 'low', 'close', 'volume')
            """
            )
            result = await session.execute(check_query)
            existing_columns = [row[0] for row in result.fetchall()]

            # Добавляем недостающие колонки
            columns_to_add = ["open", "high", "low", "close", "volume"]
            for col in columns_to_add:
                if col not in existing_columns:
                    add_column_query = text(
                        f"ALTER TABLE indicators ADD COLUMN {col} NUMERIC"
                    )
                    await session.execute(add_column_query)
                    print(f"✅ Добавлена колонка {col}")
                else:
                    print(f"ℹ️ Колонка {col} уже существует")

            await session.commit()
            print("🎉 Миграция завершена успешно")

        except Exception as e:
            print(f"❌ Ошибка при миграции: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(migrate_add_ohlcv_columns())
