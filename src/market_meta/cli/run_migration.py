"""CLI для запуска SQL миграций.

Использование:
    python -m src.market_meta.cli.run_migration 006 --dry-run
    python -m src.market_meta.cli.run_migration 006 --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from ..infrastructure.config import get_database_url


def main() -> int:
    """Запуск миграции."""
    parser = argparse.ArgumentParser(description="Run SQL migration")
    parser.add_argument("migration", help="Migration number (e.g. 006)")
    parser.add_argument("--apply", action="store_true", help="Apply migration")
    parser.add_argument("--dry-run", action="store_true", help="Show SQL only")
    args = parser.parse_args()

    migrations_dir = Path(__file__).parent.parent / "migrations"
    migration_files = list(migrations_dir.glob(f"{args.migration}*.sql"))

    if not migration_files:
        print(f"Migration {args.migration} not found in {migrations_dir}")
        return 1

    migration_file = migration_files[0]
    sql = migration_file.read_text(encoding="utf-8")

    print(f"=== Migration: {migration_file.name} ===")
    print(sql)
    print("=" * 50)

    if args.dry_run or not args.apply:
        print("[DRY-RUN] Add --apply to execute")
        return 0

    db_url = get_database_url()
    engine = create_engine(db_url)

    with engine.begin() as conn:
        # Split by statements (simple approach)
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                print(f"Executing: {stmt[:60]}...")
                conn.execute(text(stmt))

    print("[OK] Migration applied successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
