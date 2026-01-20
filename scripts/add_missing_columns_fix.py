#!/usr/bin/env python3
"""
Добавление недостающих колонок в таблицу indicators
"""

import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from sqlalchemy import text

from src.database import create_session
from src.db.db_schema_utils import ensure_columns


async def add_missing_columns():
    """Добавить недостающие колонки в таблицу indicators."""
    print("Добавление недостающих колонок в таблицу indicators...")

    # Устанавливаем переменную окружения для URL базы данных
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo"
    )

    session = await create_session()

    try:
        # Список колонок, которые нужно добавить
        # Основываясь на ошибке 'hl2' и анализе overlap.py
        missing_columns = [
            "hl2",  # (high+low)/2
            "hlc3",  # (high+low+close)/3
            "ohlc4",  # (open+high+low+close)/4
            "wcp",  # Weighted Close Price
            "midpoint",  # alias for hl2
            "midprice",  # alias for hl2
        ]

        print(f"Добавляем колонки: {missing_columns}")

        # Добавляем колонки
        await ensure_columns(session, "indicators", missing_columns)
        print("Колонки успешно добавлены")

        # Проверяем результат
        result = await session.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND table_schema = 'public'
            AND column_name IN ('hl2', 'hlc3', 'ohlc4', 'wcp', 'midpoint', 'midprice')
            ORDER BY column_name
        """
            )
        )

        existing_columns = [row[0] for row in result.fetchall()]
        print(f"Добавленные колонки: {existing_columns}")

        missing_after = [col for col in missing_columns if col not in existing_columns]
        if missing_after:
            print(f"Не удалось добавить: {missing_after}")
        else:
            print("Все колонки успешно добавлены!")

    except Exception as e:
        print(f"Ошибка: {e}")
        raise
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(add_missing_columns())
