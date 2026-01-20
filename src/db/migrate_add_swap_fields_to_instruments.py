"""
Миграция для добавления SWAP полей в таблицу instruments.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import get_async_session


async def migrate_add_swap_fields_to_instruments():
    """Добавляет SWAP поля в таблицу instruments"""

    print("🔧 Миграция: Добавление SWAP полей в таблицу instruments")
    print("=" * 80)

    async for session in get_async_session():
        try:
            # Проверяем существующие колонки
            check_columns_query = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'instruments'
                AND column_name IN ('margin_mode', 'tick_size', 'lot_size', 'maker_fee', 'taker_fee', 'maintenance_margin_rate', 'max_leverage', 'funding_rate')
                ORDER BY column_name;
            """
            )

            result = await session.execute(check_columns_query)
            existing_columns = [row[0] for row in result.fetchall()]

            print(f"📋 Существующие SWAP колонки: {existing_columns}")

            # Список колонок для добавления
            columns_to_add = [
                ("margin_mode", "character varying DEFAULT 'isolated'"),
                ("tick_size", "numeric"),
                ("lot_size", "numeric"),
                ("maker_fee", "numeric"),
                ("taker_fee", "numeric"),
                ("maintenance_margin_rate", "numeric"),
                ("max_leverage", "smallint"),
                ("funding_rate", "numeric"),
            ]

            # Добавляем только отсутствующие колонки
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    add_column_query = text(
                        f"""
                        ALTER TABLE instruments
                        ADD COLUMN {column_name} {column_type};
                    """
                    )

                    print(f"➕ Добавляем колонку: {column_name}")
                    await session.execute(add_column_query)
                else:
                    print(f"✅ Колонка уже существует: {column_name}")

            await session.commit()
            print("✅ Миграция завершена успешно!")

        except Exception as e:
            print(f"❌ Ошибка при миграции: {e}")
            await session.rollback()
        finally:
            break


if __name__ == "__main__":
    asyncio.run(migrate_add_swap_fields_to_instruments())
