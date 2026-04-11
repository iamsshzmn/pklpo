"""Generate ALTER TABLE SQL for missing columns on public.indicators_p.

The script compares the live DB schema of `indicators_p` against the code-level
SQLAlchemy model `src.features.infrastructure.models.Indicator` and emits
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` statements for missing columns.

Usage:
    python scripts/generate_indicators_parent_alter_sql.py
    python scripts/generate_indicators_parent_alter_sql.py --output sql/indicators_sync.sql
    python scripts/generate_indicators_parent_alter_sql.py --database-url <url>
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.features.infrastructure.models import Indicator
from src.features.storage_contract import IndicatorStorageContract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate ALTER TABLE SQL for missing columns on public.indicators_p "
            "based on the code-level Indicator model."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Database URL. Defaults to DATABASE_URL environment variable.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional file path to save the generated SQL.",
    )
    return parser.parse_args()


async def load_live_columns(database_url: str, table_name: str) -> list[str]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table_name
                    ORDER BY ordinal_position
                    """
                ),
                {"table_name": table_name},
            )
            return [row[0] for row in result.fetchall()]
    finally:
        await engine.dispose()


def render_column_type(column) -> str:
    """Render a SQLAlchemy column type to PostgreSQL SQL."""
    return column.type.compile(dialect=postgresql.dialect())


def build_missing_column_sql(live_columns: set[str]) -> tuple[list[str], list[str]]:
    """Return missing columns and corresponding ALTER statements."""
    statements: list[str] = []
    missing_columns: list[str] = []

    for column in Indicator.__table__.columns:
        name = column.name
        if name in live_columns:
            continue

        col_type_sql = render_column_type(column)
        nullable_sql = "" if column.nullable else " NOT NULL"
        default_sql = ""
        if column.server_default is not None:
            default_sql = f" DEFAULT {column.server_default.arg}"

        statements.append(
            "ALTER TABLE public."
            f"{IndicatorStorageContract.table_name} "
            f"ADD COLUMN IF NOT EXISTS {name} {col_type_sql}{default_sql}{nullable_sql};"
        )
        missing_columns.append(name)

    return missing_columns, statements


def build_sql_document(missing_columns: list[str], statements: list[str]) -> str:
    header = [
        f"-- Target table: public.{IndicatorStorageContract.table_name}",
        f"-- Missing columns detected: {len(missing_columns)}",
        "-- Generated from src.features.infrastructure.models.Indicator",
        "",
    ]
    return "\n".join(header + statements) + ("\n" if statements else "")


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    live_columns = asyncio.run(
        load_live_columns(args.database_url, IndicatorStorageContract.table_name)
    )
    missing_columns, statements = build_missing_column_sql(set(live_columns))
    sql_document = build_sql_document(missing_columns, statements)

    print("=" * 80)
    print("INDICATORS_P ALTER SQL GENERATOR")
    print("=" * 80)
    print(f"Live columns: {len(live_columns)}")
    print(f"Missing columns: {len(missing_columns)}")
    if missing_columns:
        print("Missing sample:", ", ".join(missing_columns[:25]))
    else:
        print("No missing columns detected.")

    print()
    print(sql_document if sql_document.strip() else "-- No ALTER statements required.")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(sql_document, encoding="utf-8")
        print(f"Saved SQL to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
