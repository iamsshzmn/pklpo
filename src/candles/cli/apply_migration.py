"""CLI for applying SQL migrations (candles).

Usage:
    python -m src.candles.cli.apply_migration 006 --dry-run
    python -m src.candles.cli.apply_migration 006 --apply
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine, text


def main() -> None:
    """Apply SQL migration."""
    parser = argparse.ArgumentParser(description="Apply SQL migrations")
    parser.add_argument("migration", help="Migration number (e.g. 006)")
    parser.add_argument("--apply", action="store_true", help="Apply migration")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Database URL (defaults to DATABASE_URL env var)",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("Error: DATABASE_URL is not set")
        print("Set the environment variable or pass --database-url")
        return

    # Find migration file
    migrations_dir = Path(__file__).parent.parent / "migrations"
    migration_files = list(migrations_dir.glob(f"{args.migration}*.sql"))

    if not migration_files:
        print(f"Migration {args.migration} not found in {migrations_dir}")
        return

    migration_file = migration_files[0]
    sql_content = migration_file.read_text(encoding="utf-8")

    print(f"Migration: {migration_file.name}")
    print("-" * 50)
    print(sql_content)
    print("-" * 50)

    if not args.apply:
        print("\n[DRY-RUN] Add --apply to execute")
        return

    engine = create_engine(args.database_url)
    with engine.begin() as conn:
        # Strip BEGIN/COMMIT since begin() already creates a transaction
        clean_sql = sql_content.replace("BEGIN;", "").replace("COMMIT;", "")
        conn.execute(text(clean_sql))

    print("\n[OK] Migration applied successfully")


if __name__ == "__main__":
    main()
