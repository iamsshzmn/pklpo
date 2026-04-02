"""Migration 300: ensure runtime service columns exist on indicators_p."""

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_add_indicators_parent_service_columns() -> None:
    async with get_db_session() as session:
        parent_exists = bool(
            (
                await session.execute(
                    text("SELECT to_regclass('public.indicators_p') IS NOT NULL")
                )
            ).scalar()
        )
        if not parent_exists:
            logger.info(
                "skip indicators_p service column sync: indicators_p does not exist yet"
            )
            return

        for column_name, column_ddl in (
            ("calculated_at", "TIMESTAMPTZ"),
            ("data_status", "VARCHAR(10) DEFAULT 'ok'"),
            ("failed_groups", "TEXT"),
            ("cdl_doji", "SMALLINT"),
            ("cdl_inside", "SMALLINT"),
        ):
            await session.execute(
                text(
                    f"ALTER TABLE indicators_p ADD COLUMN IF NOT EXISTS {column_name} "
                    f"{column_ddl}"
                )
            )

        logger.info("indicators_p service columns synchronized")
