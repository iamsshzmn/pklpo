#!/usr/bin/env python3
"""
Проверка наличия конкретных колонок в таблице indicators.
Полезно для диагностики ошибок Metabase.
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

# Колонки, которые могут вызывать проблемы
PROBLEMATIC_COLUMNS = [
    # Удалённые OHLCV
    "close",
    "high",
    "low",
    "open",
    "volume",
    # Удалённые служебные
    "data_status",
    "failed_groups",
    # Deprecated алиасы
    "ichimoku_a",
    "ichimoku_b",
    "tenkan",
    "kijun",
    "ultimate_osc",
    "williams_r",
    "vortex_pos",
    "vortex_neg",
    "bbands_upper",
    "bbands_middle",
    "bbands_lower",
    # Критические фичи
    "hlc3",
    "ema_8",
    "sma_20",
    "vortex",
]


async def check_columns(database_url: str) -> None:
    """Проверить наличие колонок."""
    print("=" * 70)
    print("ПРОВЕРКА КОЛОНОК В ТАБЛИЦЕ indicators")
    print("=" * 70)

    engine = create_async_engine(database_url, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Получить все существующие колонки
        result = await session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'indicators'
                ORDER BY column_name;
                """
            )
        )
        existing_columns = {row[0] for row in result.fetchall()}

        print(f"\nВсего колонок в БД: {len(existing_columns)}")

        # Проверить проблемные колонки
        print("\nПроверка проблемных колонок:")
        print("-" * 70)
        missing = []
        found = []
        for col in PROBLEMATIC_COLUMNS:
            if col in existing_columns:
                found.append(col)
                print(f"  [OK] {col} - существует")
            else:
                missing.append(col)
                print(f"  [MISSING] {col} - отсутствует")

        if missing:
            print(f"\n[WARNING] Отсутствующие колонки ({len(missing)}):")
            for col in missing:
                print(f"     - {col}")
            print(
                "\nЭти колонки могут вызывать ошибки в Metabase, если они используются в запросах."
            )

        if found:
            print(f"\n[OK] Найденные колонки ({len(found)}):")
            for col in found:
                print(f"     - {col}")

        # Поиск похожих колонок (для диагностики)
        print("\n" + "=" * 70)
        print("ПОИСК ПОХОЖИХ КОЛОНОК (для диагностики):")
        print("-" * 70)

        search_terms = ["ichimoku", "bb", "kc", "vortex", "willr", "ultosc"]
        for term in search_terms:
            matching = [c for c in existing_columns if term.lower() in c.lower()]
            if matching:
                print(f"\n  Колонки, содержащие '{term}':")
                for col in sorted(matching):
                    print(f"     - {col}")

    await engine.dispose()
    print("\n" + "=" * 70)
    print("[SUCCESS] Проверка завершена")
    print("=" * 70)


def main() -> int:
    """Основная функция."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo",
    )

    asyncio.run(check_columns(database_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
