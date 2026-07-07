"""Migration 490: drop ops.recovery_symbol_discovery (idempotent).

The table was created by migration 470 but is no longer used — managed
auto-discovery was removed in favour of curated-only universe (instruments_list.json).
DROP IF EXISTS is safe regardless of whether 470 was applied to a given DB.
"""

from __future__ import annotations

from sqlalchemy import text

from src.utils.session_utils import get_db_session


async def migrate_drop_ops_recovery_symbol_discovery() -> None:
    async with get_db_session() as session:
        await session.execute(
            text("DROP TABLE IF EXISTS ops.recovery_symbol_discovery")
        )
        await session.commit()
