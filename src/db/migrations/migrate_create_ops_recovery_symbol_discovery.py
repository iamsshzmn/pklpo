"""Migration: create ops.recovery_symbol_discovery table."""

from sqlalchemy import text

from src.utils.session_utils import get_db_session

RECOVERY_SYMBOL_DISCOVERY_STATUSES = ("active", "closed")

RECOVERY_SYMBOL_DISCOVERY_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
CREATE TABLE IF NOT EXISTS ops.recovery_symbol_discovery (
    symbol        TEXT        PRIMARY KEY,
    reason        TEXT        NOT NULL,
    status        TEXT        NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at     TIMESTAMPTZ,
    closed_reason TEXT,
    CONSTRAINT chk_recovery_symbol_discovery_status CHECK (
        status IN ('active','closed')
    )
)""".strip(),
    """
CREATE INDEX IF NOT EXISTS ix_recovery_symbol_discovery_status
ON ops.recovery_symbol_discovery (status, updated_at DESC)""".strip(),
)

RECOVERY_SYMBOL_DISCOVERY_SQL = "\n\n".join(RECOVERY_SYMBOL_DISCOVERY_STATEMENTS)


async def migrate_create_ops_recovery_symbol_discovery() -> None:
    async with get_db_session() as session:
        for statement in RECOVERY_SYMBOL_DISCOVERY_STATEMENTS:
            await session.execute(text(statement))
        await session.commit()
