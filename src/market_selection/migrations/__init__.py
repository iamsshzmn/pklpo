"""Market Selection database migrations."""

import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent


async def run_market_selection_migrations(session: AsyncSession) -> None:
    """
    Run all Market Selection SQL migrations in order.

    Migrations are idempotent (IF NOT EXISTS used throughout).
    """
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    for migration_file in migration_files:
        logger.info(f"Running migration: {migration_file.name}")
        sql = migration_file.read_text(encoding="utf-8")

        # Split by semicolons and execute each statement
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            if stmt and not stmt.startswith("--"):
                await session.execute(text(stmt))

        logger.info(f"Completed: {migration_file.name}")

    await session.commit()
    logger.info("All Market Selection migrations completed")


async def check_tables_exist(session: AsyncSession) -> dict[str, bool]:
    """Check which market_selection tables exist."""
    tables = [
        "market_scores_tf",
        "market_universe",
        "market_universe_versions",
        "market_regime_history",
    ]

    result = {}
    for table in tables:
        query = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = :table_name
            )
        """)
        row = await session.execute(query, {"table_name": table})
        result[table] = row.scalar()

    return result
