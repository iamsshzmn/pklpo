#!/usr/bin/env python3
"""
Скрипт для проверки различий между моделью Indicator и реальной схемой БД.
"""
import asyncio
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from sqlalchemy import text

from src.database import get_async_session
from src.models import Indicator


async def check_columns():
    """Проверяет различия между моделью и БД."""
    try:
        async for session in get_async_session():
            # Получаем колонки из модели
            model_columns = set(Indicator.__table__.columns.keys())
            print(f"Model columns: {len(model_columns)}")
            print(f"Model columns: {sorted(model_columns)}")

            # Получаем колонки из БД
            query = text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'indicators'
                AND table_schema = 'public'
            """
            )
            result = await session.execute(query)
            db_columns = {row[0] for row in result.fetchall()}
            print(f"DB columns: {len(db_columns)}")
            print(f"DB columns: {sorted(db_columns)}")

            # Находим различия
            missing_in_model = db_columns - model_columns
            missing_in_db = model_columns - db_columns

            print(f"Missing in model: {sorted(missing_in_model)}")
            print(f"Missing in DB: {sorted(missing_in_db)}")

            # Проверяем проблемные колонки из лога
            problematic = {"pvi", "ad", "rsx_14", "trange", "nvi", "bop", "rsx"}
            print(
                f"Problematic columns in model: {problematic.intersection(model_columns)}"
            )
            print(f"Problematic columns in DB: {problematic.intersection(db_columns)}")
            print(
                f"Problematic columns missing from model: {problematic - model_columns}"
            )

            break
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_columns())
