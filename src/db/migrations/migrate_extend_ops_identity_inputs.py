"""Migration 500: add PIT-aware identity operational inputs."""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

GAP_CLASSIFICATION_TYPES = (
    "unknown_raw_gap",
    "migration_halt",
    "market_halt",
    "recoverable_data_gap",
)
GAP_CLASSIFICATION_STATUSES = ("needs_review", "approved", "rejected")

SYMBOL_SUCCESSION_PIT_STATEMENTS = (
    """
ALTER TABLE ops.symbol_succession
ADD COLUMN IF NOT EXISTS effective_from timestamptz NULL
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
ADD COLUMN IF NOT EXISTS known_from timestamptz NOT NULL DEFAULT now()
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
ADD COLUMN IF NOT EXISTS approved_at timestamptz NULL
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
DROP CONSTRAINT IF EXISTS chk_symbol_succession_approved_at
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
ADD CONSTRAINT chk_symbol_succession_approved_at
CHECK (status <> 'approved' OR approved_at IS NOT NULL)
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
DROP CONSTRAINT IF EXISTS chk_symbol_succession_effective_from
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
ADD CONSTRAINT chk_symbol_succession_effective_from
CHECK (status <> 'approved' OR effective_from IS NOT NULL)
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
DROP CONSTRAINT IF EXISTS chk_symbol_succession_known_before_approved
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
ADD CONSTRAINT chk_symbol_succession_known_before_approved
CHECK (status <> 'approved' OR known_from <= approved_at)
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
DROP CONSTRAINT IF EXISTS chk_symbol_succession_stop_before_start
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
ADD CONSTRAINT chk_symbol_succession_stop_before_start
CHECK (old_stop_ts IS NULL OR new_start_ts IS NULL OR old_stop_ts <= new_start_ts)
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
DROP CONSTRAINT IF EXISTS chk_symbol_succession_stop_before_effective
    """.strip(),
    """
ALTER TABLE ops.symbol_succession
ADD CONSTRAINT chk_symbol_succession_stop_before_effective
CHECK (effective_from IS NULL OR old_stop_ts IS NULL OR old_stop_ts <= effective_from)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_symbol_succession_status_approved_at
ON ops.symbol_succession (status, approved_at)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_symbol_succession_build_lookup
ON ops.symbol_succession (venue, inst_type, old_symbol, new_symbol, known_from)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_symbol_succession_new_symbol_known
ON ops.symbol_succession (new_symbol, known_from)
    """.strip(),
)

GAP_CLASSIFICATION_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
CREATE TABLE IF NOT EXISTS ops.gap_classification (
    id              bigserial   PRIMARY KEY,
    series_id       text        NOT NULL,
    timeframe       text        NULL,
    range_start_ts  bigint      NOT NULL,
    range_end_ts    bigint      NOT NULL,
    gap_type        text        NOT NULL,
    recoverability  text        NOT NULL DEFAULT 'unknown',
    evidence        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    asserted_by     text        NOT NULL,
    status          text        NOT NULL DEFAULT 'needs_review',
    known_from      timestamptz NOT NULL DEFAULT now(),
    approved_at     timestamptz NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_gap_classification_range
        CHECK (range_start_ts < range_end_ts),
    CONSTRAINT chk_gap_classification_type CHECK (gap_type IN (
        'unknown_raw_gap','migration_halt','market_halt','recoverable_data_gap'
    )),
    CONSTRAINT chk_gap_classification_status
        CHECK (status IN ('needs_review','approved','rejected')),
    CONSTRAINT chk_gap_classification_approved_at
        CHECK (status <> 'approved' OR approved_at IS NOT NULL),
    CONSTRAINT chk_gap_classification_known_before_approved
        CHECK (status <> 'approved' OR known_from <= approved_at)
)
    """.strip(),
    """
CREATE UNIQUE INDEX IF NOT EXISTS ux_gap_classification_identity
ON ops.gap_classification (
    series_id,
    COALESCE(timeframe, '*'),
    range_start_ts,
    range_end_ts,
    gap_type,
    known_from
)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_gap_classification_approved
ON ops.gap_classification (status, approved_at, known_from)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_gap_classification_series_range
ON ops.gap_classification (series_id, timeframe, range_start_ts, range_end_ts)
    """.strip(),
)

SYMBOL_SUCCESSION_PIT_SQL = ";\n\n".join(SYMBOL_SUCCESSION_PIT_STATEMENTS) + ";"
GAP_CLASSIFICATION_SQL = ";\n\n".join(GAP_CLASSIFICATION_STATEMENTS) + ";"
OPS_IDENTITY_INPUTS_STATEMENTS = (
    *SYMBOL_SUCCESSION_PIT_STATEMENTS,
    *GAP_CLASSIFICATION_STATEMENTS,
)
OPS_IDENTITY_INPUTS_SQL = ";\n\n".join(OPS_IDENTITY_INPUTS_STATEMENTS) + ";"


async def migrate_extend_ops_identity_inputs() -> None:
    """Ensure PIT-aware succession fields and gap classification input table."""
    async with get_db_session() as session:
        try:
            for statement in OPS_IDENTITY_INPUTS_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("ops identity input tables ensured")
        except Exception:
            await session.rollback()
            raise
