#!/usr/bin/env python3
"""
Проверка подключения к БД и наличия таблицы indicators.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


async def check_database(database_url: str) -> None:
    """Проверить подключение и наличие таблицы."""
    print("=" * 70)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БД")
    print("=" * 70)
    print(
        f"\nURL: {database_url.split('@')[-1] if '@' in database_url else database_url}"
    )

    try:
        engine = create_async_engine(database_url, future=True)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            # Проверка подключения
            print("\n1. Проверка подключения...")
            result = await session.execute(text("SELECT version();"))
            version = result.scalar()
            print("   [OK] Подключение успешно")
            print(f"   PostgreSQL версия: {version.split(',')[0]}")

            # Проверка наличия базы данных
            print("\n2. Проверка текущей базы данных...")
            result = await session.execute(text("SELECT current_database();"))
            db_name = result.scalar()
            print(f"   [OK] Текущая БД: {db_name}")

            # Проверка наличия таблицы indicators
            print("\n3. Проверка наличия таблицы indicators...")
            result = await session.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'indicators'
                    );
                    """
                )
            )
            table_exists = result.scalar()
            if table_exists:
                print("   [OK] Таблица indicators существует")

                # Количество строк
                result = await session.execute(
                    text("SELECT COUNT(*) FROM public.indicators;")
                )
                row_count = result.scalar()
                print(f"   Количество строк: {row_count:,}")

                # Количество колонок
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = 'indicators';
                        """
                    )
                )
                col_count = result.scalar()
                print(f"   Количество колонок: {col_count}")

                # Список колонок (первые 20)
                result = await session.execute(
                    text(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = 'indicators'
                        ORDER BY column_name
                        LIMIT 20;
                        """
                    )
                )
                print("\n   Первые 20 колонок:")
                for row in result.fetchall():
                    print(f"      - {row[0]} ({row[1]})")

            else:
                print("   [ERROR] Таблица indicators не найдена")

            # Проверка других таблиц
            print("\n4. Список всех таблиц в схеме public:")
            result = await session.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                    """
                )
            )
            tables = [row[0] for row in result.fetchall()]
            if tables:
                for table in tables:
                    print(f"   - {table}")
            else:
                print("   [INFO] Таблицы не найдены")

        await engine.dispose()
        print("\n" + "=" * 70)
        print("[SUCCESS] Проверка завершена")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] Ошибка подключения: {e}")
        print("\nВозможные причины:")
        print("  1. База данных не запущена")
        print("  2. Неправильные учётные данные")
        print("  3. Проблемы с сетью")
        print("\nПроверьте:")
        print("  - Docker контейнер запущен: docker ps | grep pklpo_db")
        print("  - Порт доступен: telnet localhost 5432")
        raise


def main() -> int:
    """Основная функция."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo",
    )

    asyncio.run(check_database(database_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
