import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_create_schema_migrations() -> None:
    """
    Creates the schema_migrations table if it does not exist.
    The table stores migration id, name, status, timings and error info.
    """
    create_sql = text(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at BIGINT NOT NULL,
            duration_ms INTEGER NOT NULL,
            status TEXT NOT NULL,
            attempt INTEGER NOT NULL DEFAULT 1,
            error TEXT
        );
        """
    )

    # Optional helper index to query by status quickly
    create_idx_sql = text(
        """
        CREATE INDEX IF NOT EXISTS idx_schema_migrations_status
        ON schema_migrations(status);
        """
    )

    async with get_db_session() as session:
        await session.execute(create_sql)
        await session.execute(create_idx_sql)
        await session.commit()
        logger.info("✅ Таблица schema_migrations готова")
