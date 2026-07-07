"""Migration 530: create continuous OHLCV build audit surface."""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

CONTINUOUS_OHLCV_BUILD_AUDIT_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
CREATE TABLE IF NOT EXISTS ops.continuous_ohlcv_build_audit (
    run_id TEXT PRIMARY KEY,
    series_id TEXT NOT NULL,
    timeframe TEXT NULL,
    algo_version TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    snapshot_id TEXT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz NULL,
    status TEXT NOT NULL,
    row_count integer NOT NULL DEFAULT 0,
    gap_count integer NOT NULL DEFAULT 0,
    segment_count integer NOT NULL DEFAULT 0,
    error_type TEXT NULL,
    error_message_hash TEXT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_continuous_ohlcv_build_audit_status
        CHECK (status IN ('success','failed'))
)
    """.strip(),
    """
CREATE TABLE IF NOT EXISTS core.continuous_ohlcv_default
PARTITION OF core.continuous_ohlcv_p DEFAULT
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_continuous_ohlcv_build_audit_series
ON ops.continuous_ohlcv_build_audit (series_id, timeframe, status)
    """.strip(),
)

CONTINUOUS_OHLCV_BUILD_AUDIT_SQL = (
    ";\n\n".join(CONTINUOUS_OHLCV_BUILD_AUDIT_STATEMENTS) + ";"
)


async def migrate_create_continuous_ohlcv_build_audit() -> None:
    """Create continuous build audit table and default OHLCV partition."""
    async with get_db_session() as session:
        try:
            for statement in CONTINUOUS_OHLCV_BUILD_AUDIT_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("continuous OHLCV build audit ensured")
        except Exception:
            await session.rollback()
            raise
