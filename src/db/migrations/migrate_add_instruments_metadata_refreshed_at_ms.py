from __future__ import annotations

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def migrate_add_instruments_metadata_refreshed_at_ms() -> None:
    """Add persisted instrument catalog refresh time and backfill existing rows."""

    async with get_db_session() as session:
        try:
            await session.execute(
                text(
                    """
                    ALTER TABLE instruments
                    ADD COLUMN IF NOT EXISTS metadata_refreshed_at_ms BIGINT
                    """
                )
            )
            await session.execute(
                text(
                    """
                    UPDATE instruments
                    SET metadata_refreshed_at_ms = COALESCE(
                        metadata_refreshed_at_ms,
                        list_time,
                        (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
                    )
                    """
                )
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
