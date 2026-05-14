"""Migration 330: extend ops.swap_repair_audit with semantic fields.

Adds nullable columns to capture outcome classification and repair
progress observability. Idempotent (ADD COLUMN IF NOT EXISTS), no
backfill: historical rows keep NULL.
"""

from sqlalchemy import text

from src.utils.session_utils import get_db_session

_ALTER_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE ops.swap_repair_audit ADD COLUMN IF NOT EXISTS outcome TEXT NULL;",
    "ALTER TABLE ops.swap_repair_audit ADD COLUMN IF NOT EXISTS received_bars INTEGER NULL;",
    "ALTER TABLE ops.swap_repair_audit ADD COLUMN IF NOT EXISTS "
    "remaining_missing_before INTEGER NULL;",
    "ALTER TABLE ops.swap_repair_audit ADD COLUMN IF NOT EXISTS "
    "remaining_missing_after INTEGER NULL;",
    "ALTER TABLE ops.swap_repair_audit ADD COLUMN IF NOT EXISTS progress INTEGER NULL;",
    "ALTER TABLE ops.swap_repair_audit ADD COLUMN IF NOT EXISTS "
    "api_fill_ratio DOUBLE PRECISION NULL;",
    "ALTER TABLE ops.swap_repair_audit ADD COLUMN IF NOT EXISTS "
    "write_success_ratio DOUBLE PRECISION NULL;",
)


async def migrate_extend_ops_swap_repair_audit_semantics() -> None:
    async with get_db_session() as session:
        for statement in _ALTER_STATEMENTS:
            await session.execute(text(statement))
        await session.commit()
