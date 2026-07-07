"""Migration: create ops.symbol_succession table."""

from sqlalchemy import text

from src.utils.session_utils import get_db_session

SYMBOL_SUCCESSION_STATUSES = ("needs_review", "approved", "rejected")
SYMBOL_SUCCESSION_EVENT_TYPES = (
    "ticker_change",
    "token_migration",
    "redenomination",
    "delisting",
    "relisting",
    "contract_upgrade",
    "hard_fork",
    "merge",
    "split",
)

SYMBOL_SUCCESSION_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
CREATE TABLE IF NOT EXISTS ops.symbol_succession (
    old_symbol               text        NOT NULL,
    new_symbol               text        NOT NULL,
    inst_type                text        NOT NULL,
    venue                    text        NOT NULL DEFAULT 'OKX',
    event_type               text        NOT NULL,
    ratio                    numeric     NOT NULL DEFAULT 1,
    old_stop_ts              timestamptz NULL,
    new_start_ts             timestamptz NULL,
    price_continuity_checked boolean     NOT NULL DEFAULT false,
    contract_specs_checked   boolean     NOT NULL DEFAULT false,
    source_url               text        NULL,
    status                   text        NOT NULL DEFAULT 'needs_review',
    notes                    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (venue, inst_type, old_symbol, new_symbol),
    CONSTRAINT chk_symbol_succession_status
        CHECK (status IN ('needs_review','approved','rejected')),
    CONSTRAINT chk_symbol_succession_ratio_positive CHECK (ratio > 0),
    CONSTRAINT chk_symbol_succession_event_type CHECK (event_type IN (
        'ticker_change','token_migration','redenomination',
        'delisting','relisting','contract_upgrade','hard_fork','merge','split'))
)""".strip(),
    """
CREATE INDEX IF NOT EXISTS ix_symbol_succession_new_symbol
ON ops.symbol_succession (new_symbol)""".strip(),
    """
CREATE INDEX IF NOT EXISTS ix_symbol_succession_status
ON ops.symbol_succession (status)""".strip(),
)

SYMBOL_SUCCESSION_SQL = "\n\n".join(SYMBOL_SUCCESSION_STATEMENTS)


async def migrate_create_ops_symbol_succession() -> None:
    async with get_db_session() as session:
        for statement in SYMBOL_SUCCESSION_STATEMENTS:
            await session.execute(text(statement))
        await session.commit()
