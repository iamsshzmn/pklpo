from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

RETENTION_POLICY: dict[str, int | None] = {
    "1m": 2,
    "5m": 7,
    "15m": 14,
    "30m": 30,
    "1H": 14,
    "4H": 60,
    "1D": 400,
    "1W": None,
    "1M": None,
}

_VALUES_SQL = ",\n".join(
    f"('{timeframe}', {days if days is not None else 'NULL'})"
    for timeframe, days in RETENTION_POLICY.items()
)

SWAP_OHLCV_RETENTION_STATEMENTS: tuple[str, ...] = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
CREATE TABLE IF NOT EXISTS swap_ohlcv_retention_policy (
    timeframe TEXT PRIMARY KEY,
    retention_days INTEGER NULL CHECK (retention_days IS NULL OR retention_days > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)""",
    f"""
INSERT INTO swap_ohlcv_retention_policy (timeframe, retention_days)
VALUES
{_VALUES_SQL}
ON CONFLICT (timeframe) DO UPDATE
SET retention_days = EXCLUDED.retention_days,
    updated_at = NOW()""",
    """
CREATE TABLE IF NOT EXISTS ops.swap_ohlcv_cleanup_audit (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    cutoff_timestamp BIGINT NULL,
    deleted_count BIGINT NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    triggered_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)""",
    "DROP TRIGGER IF EXISTS trigger_cleanup_swap_data ON swap_ohlcv_p",
    """
DO $$
DECLARE
    trigger_record RECORD;
BEGIN
    FOR trigger_record IN
        SELECT tg.tgname AS trigger_name, tg.tgrelid::regclass AS table_name
        FROM pg_trigger tg
        WHERE tg.tgname = 'trigger_cleanup_swap_data'
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS %I ON %s',
            trigger_record.trigger_name,
            trigger_record.table_name
        );
    END LOOP;
END
$$""",
    "DROP FUNCTION IF EXISTS trigger_cleanup_old_data()",
    "DROP FUNCTION IF EXISTS cleanup_old_swap_data()",
    "DROP FUNCTION IF EXISTS manual_cleanup_swap_data(INTEGER)",
    """
CREATE OR REPLACE FUNCTION cleanup_old_swap_data(
    p_triggered_by TEXT DEFAULT 'maintenance',
    p_run_id TEXT DEFAULT NULL
)
RETURNS TABLE(
    timeframe TEXT,
    cutoff_timestamp BIGINT,
    deleted_count BIGINT,
    duration_ms INTEGER,
    skipped_reason TEXT
) AS $$
DECLARE
    policy RECORD;
    run_identifier TEXT;
    started_at TIMESTAMPTZ;
    cutoff_ts BIGINT;
    deleted_cnt BIGINT;
    elapsed_ms INTEGER;
BEGIN
    run_identifier := COALESCE(
        NULLIF(p_run_id, ''),
        'swap-cleanup-' || to_char(clock_timestamp(), 'YYYYMMDDHH24MISSMS')
    );

    FOR policy IN
        SELECT p.timeframe, p.retention_days
        FROM swap_ohlcv_retention_policy p
        ORDER BY p.timeframe
    LOOP
        IF policy.retention_days IS NULL THEN
            INSERT INTO ops.swap_ohlcv_cleanup_audit (
                run_id, timeframe, cutoff_timestamp, deleted_count, duration_ms, triggered_by
            )
            VALUES (run_identifier, policy.timeframe, NULL, 0, 0, p_triggered_by);

            RAISE NOTICE 'Skipped swap_ohlcv_p cleanup for %, reason=infinite_retention',
                policy.timeframe;

            timeframe := policy.timeframe;
            cutoff_timestamp := NULL;
            deleted_count := 0;
            duration_ms := 0;
            skipped_reason := 'infinite_retention';
            RETURN NEXT;
            CONTINUE;
        END IF;

        started_at := clock_timestamp();
        cutoff_ts := (
            EXTRACT(EPOCH FROM NOW() - make_interval(days => policy.retention_days)) * 1000
        )::BIGINT;

        DELETE FROM swap_ohlcv_p c
        WHERE c.timeframe = policy.timeframe
          AND c.timestamp < cutoff_ts;

        GET DIAGNOSTICS deleted_cnt = ROW_COUNT;
        elapsed_ms := GREATEST(
            0,
            (EXTRACT(EPOCH FROM (clock_timestamp() - started_at)) * 1000)::INTEGER
        );

        INSERT INTO ops.swap_ohlcv_cleanup_audit (
            run_id, timeframe, cutoff_timestamp, deleted_count, duration_ms, triggered_by
        )
        VALUES (
            run_identifier,
            policy.timeframe,
            cutoff_ts,
            deleted_cnt,
            elapsed_ms,
            p_triggered_by
        );

        RAISE NOTICE 'Cleaned swap_ohlcv_p timeframe %, deleted %, cutoff %, duration_ms %',
            policy.timeframe, deleted_cnt, cutoff_ts, elapsed_ms;

        timeframe := policy.timeframe;
        cutoff_timestamp := cutoff_ts;
        deleted_count := deleted_cnt;
        duration_ms := elapsed_ms;
        skipped_reason := NULL;
        RETURN NEXT;
    END LOOP;
END;
$$ LANGUAGE plpgsql""",
    """
CREATE OR REPLACE FUNCTION manual_cleanup_swap_data(
    p_triggered_by TEXT DEFAULT 'manual'
)
RETURNS TABLE(
    timeframe TEXT,
    cutoff_timestamp BIGINT,
    deleted_count BIGINT,
    duration_ms INTEGER,
    skipped_reason TEXT
) AS $$
BEGIN
    RETURN QUERY SELECT * FROM cleanup_old_swap_data(p_triggered_by);
END;
$$ LANGUAGE plpgsql""",
)

SWAP_OHLCV_RETENTION_SQL = ";\n\n".join(SWAP_OHLCV_RETENTION_STATEMENTS)


async def migrate_swap_ohlcv_retention_policy() -> None:
    """Replace insert-trigger cleanup with policy-driven maintenance cleanup."""
    async with get_db_session() as session:
        try:
            for statement in SWAP_OHLCV_RETENTION_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("swap_ohlcv_p retention policy migration applied")
        except Exception:
            await session.rollback()
            raise
