#!/usr/bin/env python3
"""
Восстановление и очистка схемы indicators.

Действия:
1. Восстановить vortex (отсутствует в БД, но рассчитывается)
2. Удалить OHLCV колонки (close, high, low, open, volume)
3. Удалить служебные поля (data_status, failed_groups)

Безопасный скрипт с dry-run по умолчанию. Для применения использовать флаг --apply.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Колонки к восстановлению
RESTORE_COLUMNS: list[tuple[str, str]] = [
    ("vortex", "DECIMAL"),
]

# Колонки к удалению
DROP_COLUMNS: list[str] = [
    # OHLCV данные (не должны быть в indicators)
    "close",
    "high",
    "low",
    "open",
    "volume",
    # Служебные поля
    "data_status",
    "failed_groups",
]


async def get_existing_columns(session: AsyncSession) -> set[str]:
    """Получить список существующих колонок."""
    result = await session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'indicators'
            ORDER BY column_name
            """
        )
    )
    return {row[0] for row in result.fetchall()}


async def restore_column(
    session: AsyncSession, column_name: str, column_type: str, apply: bool
) -> None:
    """Восстановить колонку."""
    if not apply:
        print(
            f"  [DRY-RUN] ALTER TABLE public.indicators ADD COLUMN {column_name} {column_type};"
        )
        return
    await session.execute(
        text(
            f"ALTER TABLE public.indicators ADD COLUMN IF NOT EXISTS {column_name} {column_type}"
        )
    )
    print(f"  [OK] Восстановлена колонка: {column_name}")


async def drop_column(session: AsyncSession, column_name: str, apply: bool) -> None:
    """Удалить колонку."""
    if not apply:
        print(
            f"  [DRY-RUN] ALTER TABLE public.indicators DROP COLUMN IF EXISTS {column_name};"
        )
        return
    await session.execute(
        text(f"ALTER TABLE public.indicators DROP COLUMN IF EXISTS {column_name}")
    )
    print(f"  [OK] Удалена колонка: {column_name}")


async def main(apply: bool) -> int:
    """Основная функция."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo",
    )

    engine = create_async_engine(database_url, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=" * 70)
    if apply:
        print("РЕЖИМ: ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ")
    else:
        print("РЕЖИМ: DRY-RUN (показать план без применения)")
    print("=" * 70)
    print(
        f"\nБаза данных: {database_url.split('@')[-1] if '@' in database_url else database_url}"
    )
    print("\nРекомендуемый бэкап:")
    print(
        "  docker exec pklpo_db pg_dump -U pklpo_user pklpo > backup_before_schema_fix.sql"
    )
    print("  ИЛИ")
    print("  pg_dump -h localhost -U pklpo_user pklpo > backup_before_schema_fix.sql")
    print()

    async with async_session() as session:
        existing = await get_existing_columns(session)

        # Восстановление колонок
        print("\n1. ВОССТАНОВЛЕНИЕ КОЛОНОК:")
        restore_count = 0
        for col_name, col_type in RESTORE_COLUMNS:
            if col_name not in existing:
                await restore_column(session, col_name, col_type, apply)
                restore_count += 1
            else:
                print(f"  [SKIP] Колонка {col_name} уже существует")
        if restore_count == 0:
            print("  [INFO] Нет колонок к восстановлению")

        # Удаление колонок
        print("\n2. УДАЛЕНИЕ КОЛОНОК:")
        drop_count = 0
        for col_name in DROP_COLUMNS:
            if col_name in existing:
                await drop_column(session, col_name, apply)
                drop_count += 1
            else:
                print(f"  [SKIP] Колонка {col_name} не существует")
        if drop_count == 0:
            print("  [INFO] Нет колонок к удалению")

        if apply:
            await session.commit()
            print("\n[SUCCESS] Изменения применены")
        else:
            await session.rollback()
            print("\n[INFO] Dry-run завершён. Для применения запустите с --apply")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Восстановление и очистка схемы indicators"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Применить изменения (по умолчанию: dry-run)",
    )
    args = parser.parse_args()

    import asyncio

    raise SystemExit(asyncio.run(main(args.apply)))
