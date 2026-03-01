#!/usr/bin/env python3
"""
Очистка устаревших/дублирующих колонок из public.indicators.

Безопасный скрипт с dry-run по умолчанию. Для применения использовать флаг --apply.
Печатает план изменений и рекомендуемый путь бэкапа.
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DEPRECATED_COLUMNS: list[str] = [
    # bbands duplicates
    "bbands_upper",
    "bbands_middle",
    "bbands_lower",
    "bbands_percent",
    "bbands_width",
    # ichimoku aliases/duplicates
    "ichimoku_a",
    "ichimoku_b",
    "tenkan",
    "kijun",
    # oscillators legacy
    "ultimate_osc",
    "williams_r",
    "vortex",
    "vortex_pos",
    "vortex_neg",
    # misc duplicates
    "bb_percent",
    "bb_width",
]


async def get_existing_columns(session: AsyncSession) -> list[str]:
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'indicators'
        ORDER BY column_name
        """
    )
    res = await session.execute(q)
    return [r[0] for r in res.fetchall()]


def print_plan(existing: list[str], target: list[str], backup_dir: str) -> None:
    to_drop = [c for c in target if c in existing]
    keep_missing = [c for c in target if c not in existing]

    print("\n=== PLAN: Cleanup deprecated columns from public.indicators ===")
    print(f"Backup path (recommendation): {backup_dir}")
    print("Will drop (existing):" if to_drop else "Nothing to drop")
    for c in to_drop:
        print(f"  - {c}")
    if keep_missing:
        print("Already absent (skip):")
        for c in keep_missing:
            print(f"  - {c}")
    print("==============================================================\n")


async def apply_drop(session: AsyncSession, to_drop: list[str]) -> None:
    if not to_drop:
        print("Nothing to apply.")
        return
    print("Applying migration in a single transaction...")
    await session.execute(text("BEGIN"))
    try:
        for col in to_drop:
            stmt = text(f"ALTER TABLE public.indicators DROP COLUMN {col}")
            await session.execute(stmt)
            print(f"  dropped: {col}")
        await session.commit()
        print("Committed.")
    except Exception as e:
        await session.rollback()
        print(f"Rollback due to error: {e}")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup deprecated indicator columns")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Применить изменения (по умолчанию dry-run)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://pklpo_user:strongpassword@localhost:5432/pklpo",
        ),
        help="Строка подключения к БД SQLAlchemy async",
    )
    parser.add_argument(
        "--backup-path",
        default=os.path.join(os.getcwd(), "backups", "indicators_ddl_backup.sql"),
        help="Куда сохранить бэкап перед применением (рекомендация)",
    )
    args = parser.parse_args()

    engine = create_async_engine(args.database_url, future=True)

    async def run() -> int:
        async_session_factory = sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            existing = await get_existing_columns(session)
            print_plan(existing, DEPRECATED_COLUMNS, args.backup_path)
            if not args.apply:
                print("Dry-run complete. Re-run with --apply to execute.")
                return 0
            to_drop = [c for c in DEPRECATED_COLUMNS if c in existing]
            await apply_drop(session, to_drop)
            return 0

    try:
        import asyncio

        return asyncio.run(run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
