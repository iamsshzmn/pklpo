"""Migration 510: create core identity tables."""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

SERIES_KINDS = ("trivial", "composite")
SERIES_STATUSES = ("active", "retired", "superseded")
SERIES_GAP_TYPES = (
    "unknown_raw_gap",
    "migration_halt",
    "market_halt",
    "recoverable_data_gap",
)
SERIES_DATA_STATUSES = ("complete", "partial", "missing", "invalid", "warmup")

CORE_IDENTITY_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS core",
    """
CREATE TABLE IF NOT EXISTS core.series_registry (
    series_id TEXT PRIMARY KEY,
    series_label TEXT NOT NULL,
    asset_id TEXT NULL,
    series_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    kind_current_since timestamptz NOT NULL DEFAULT now(),
    status_current_since timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_series_registry_kind
        CHECK (series_kind IN ('trivial','composite')),
    CONSTRAINT chk_series_registry_status
        CHECK (status IN ('active','retired','superseded'))
)
    """.strip(),
    """
CREATE TABLE IF NOT EXISTS core.series_members (
    series_id TEXT NOT NULL REFERENCES core.series_registry(series_id),
    source_venue TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    valid_from bigint NOT NULL,
    valid_to bigint NULL,
    known_from timestamptz NOT NULL,
    known_to timestamptz NULL,
    adjustment_factor NUMERIC NOT NULL DEFAULT 1,
    succession_id TEXT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (series_id, source_venue, source_symbol, valid_from, known_from),
    CONSTRAINT chk_series_members_valid_range
        CHECK (valid_to IS NULL OR valid_from < valid_to),
    CONSTRAINT chk_series_members_known_range
        CHECK (known_to IS NULL OR known_from < known_to),
    CONSTRAINT chk_series_members_adjustment_factor
        CHECK (adjustment_factor > 0)
)
    """.strip(),
    """
CREATE TABLE IF NOT EXISTS core.series_alias (
    old_series_id TEXT NOT NULL,
    canonical_series_id TEXT NOT NULL REFERENCES core.series_registry(series_id),
    known_from timestamptz NOT NULL,
    known_to timestamptz NULL,
    reason TEXT NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (old_series_id, canonical_series_id, known_from),
    CONSTRAINT chk_series_alias_known_range
        CHECK (known_to IS NULL OR known_from < known_to)
)
    """.strip(),
    """
CREATE TABLE IF NOT EXISTS core.series_segments (
    series_id TEXT NOT NULL REFERENCES core.series_registry(series_id),
    timeframe TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    source_venue TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    segment_start_ts bigint NOT NULL,
    segment_end_ts bigint NULL,
    segment_order integer NOT NULL,
    reset_features_from_here boolean NOT NULL DEFAULT true,
    known_from timestamptz NOT NULL,
    known_to timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (series_id, timeframe, segment_id, known_from),
    CONSTRAINT chk_series_segments_ts_range
        CHECK (segment_end_ts IS NULL OR segment_start_ts < segment_end_ts),
    CONSTRAINT chk_series_segments_known_range
        CHECK (known_to IS NULL OR known_from < known_to)
)
    """.strip(),
    """
CREATE TABLE IF NOT EXISTS core.series_gap_ranges (
    series_id TEXT NOT NULL REFERENCES core.series_registry(series_id),
    timeframe TEXT NOT NULL,
    gap_start_ts bigint NOT NULL,
    gap_end_ts bigint NOT NULL,
    gap_type TEXT NOT NULL,
    old_symbol TEXT NULL,
    new_symbol TEXT NULL,
    succession_id TEXT NULL,
    recoverability TEXT NOT NULL DEFAULT 'unknown',
    reason TEXT NOT NULL,
    known_from timestamptz NOT NULL,
    known_to timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (series_id, timeframe, gap_start_ts, gap_end_ts, gap_type, known_from),
    CONSTRAINT chk_series_gap_ranges_ts_range
        CHECK (gap_start_ts < gap_end_ts),
    CONSTRAINT chk_series_gap_ranges_known_range
        CHECK (known_to IS NULL OR known_from < known_to),
    CONSTRAINT chk_series_gap_ranges_type CHECK (gap_type IN (
        'unknown_raw_gap','migration_halt','market_halt','recoverable_data_gap'
    ))
)
    """.strip(),
    """
CREATE TABLE IF NOT EXISTS core.series_adjustments (
    series_id TEXT NOT NULL REFERENCES core.series_registry(series_id),
    source_venue TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    effective_ts bigint NOT NULL,
    adjustment_factor NUMERIC NOT NULL,
    reason TEXT NOT NULL,
    known_from timestamptz NOT NULL,
    known_to timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (series_id, source_venue, source_symbol, effective_ts, known_from),
    CONSTRAINT chk_series_adjustments_factor
        CHECK (adjustment_factor > 0),
    CONSTRAINT chk_series_adjustments_known_range
        CHECK (known_to IS NULL OR known_from < known_to)
)
    """.strip(),
    """
CREATE TABLE IF NOT EXISTS core.continuous_ohlcv_p (
    series_id TEXT NOT NULL REFERENCES core.series_registry(series_id),
    timeframe TEXT NOT NULL,
    timestamp bigint NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    source_venue TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    source_timestamp bigint NOT NULL,
    segment_id TEXT NOT NULL,
    succession_id TEXT NULL,
    adjustment_factor NUMERIC NOT NULL DEFAULT 1,
    bar_kind TEXT NOT NULL,
    data_status TEXT NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    run_id TEXT NOT NULL,
    algo_version TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    snapshot_id TEXT NULL,
    PRIMARY KEY (series_id, timeframe, timestamp),
    CONSTRAINT chk_continuous_ohlcv_adjustment_factor
        CHECK (adjustment_factor > 0),
    CONSTRAINT chk_continuous_ohlcv_bar_kind
        CHECK (bar_kind IN ('native','synthetic')),
    CONSTRAINT chk_continuous_ohlcv_data_status CHECK (data_status IN (
        'complete','partial','missing','invalid','warmup'
    ))
) PARTITION BY RANGE (timestamp)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_series_members_series_range
ON core.series_members (series_id, valid_from, valid_to)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_series_members_source_range
ON core.series_members (source_venue, source_symbol, valid_from, valid_to)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_series_gap_ranges_series_range
ON core.series_gap_ranges (series_id, timeframe, gap_start_ts, gap_end_ts)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_series_segments_series_range
ON core.series_segments (series_id, timeframe, segment_start_ts, segment_end_ts)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_continuous_ohlcv_source_lookup
ON core.continuous_ohlcv_p (source_venue, source_symbol, timeframe, source_timestamp)
    """.strip(),
    """
CREATE INDEX IF NOT EXISTS ix_continuous_ohlcv_succession
ON core.continuous_ohlcv_p (succession_id)
    """.strip(),
)

CORE_IDENTITY_SQL = ";\n\n".join(CORE_IDENTITY_STATEMENTS) + ";"


async def migrate_create_core_identity() -> None:
    """Create core identity schema and base tables."""
    async with get_db_session() as session:
        try:
            for statement in CORE_IDENTITY_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("core identity tables ensured")
        except Exception:
            await session.rollback()
            raise
