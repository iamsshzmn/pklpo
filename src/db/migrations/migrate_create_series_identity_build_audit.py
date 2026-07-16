"""Migration 520: create identity build audit table."""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

SERIES_IDENTITY_BUILD_STATUSES = ("running", "success", "failed")

SERIES_IDENTITY_BUILD_AUDIT_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
CREATE TABLE IF NOT EXISTS ops.series_identity_build_audit (
    run_id TEXT PRIMARY KEY,
    algo_version TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    snapshot_id TEXT NULL,
    started_at timestamptz NOT NULL,
    finished_at timestamptz NULL,
    status TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    rows_inserted integer NOT NULL DEFAULT 0,
    rows_deleted integer NOT NULL DEFAULT 0,
    gap_count integer NOT NULL DEFAULT 0,
    segment_count integer NOT NULL DEFAULT 0,
    error_type TEXT NULL,
    error_message_hash TEXT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_series_identity_build_audit_status
        CHECK (status IN ('running','success','failed'))
)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_series_identity_build_audit_status_started
ON ops.series_identity_build_audit (status, started_at DESC)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_series_identity_build_audit_finished
ON ops.series_identity_build_audit (finished_at DESC)
    """.strip(),
)

SERIES_IDENTITY_BUILD_AUDIT_SQL = (
    ";\n\n".join(SERIES_IDENTITY_BUILD_AUDIT_STATEMENTS) + ";"
)


async def migrate_create_series_identity_build_audit() -> None:
    """Create audit table for identity build publication."""
    async with get_db_session() as session:
        try:
            for statement in SERIES_IDENTITY_BUILD_AUDIT_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("ops.series_identity_build_audit table ensured")
        except Exception:
            await session.rollback()
            raise
