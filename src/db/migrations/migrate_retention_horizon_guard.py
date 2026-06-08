from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

WARMUP_HORIZON_BARS = 500

RETENTION_HORIZON_GUARD_SQL = """
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
    tf_ms BIGINT;
    retention_cutoff_ts BIGINT;
    min_keep_ts BIGINT;
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

        tf_ms := CASE policy.timeframe
            WHEN '1m' THEN 60 * 1000
            WHEN '5m' THEN 5 * 60 * 1000
            WHEN '15m' THEN 15 * 60 * 1000
            WHEN '30m' THEN 30 * 60 * 1000
            WHEN '1H' THEN 60 * 60 * 1000
            WHEN '4H' THEN 4 * 60 * 60 * 1000
            WHEN '1D' THEN 24 * 60 * 60 * 1000
            WHEN '1W' THEN 7 * 24 * 60 * 60 * 1000
            ELSE NULL
        END;

        retention_cutoff_ts := (
            EXTRACT(EPOCH FROM NOW() - make_interval(days => policy.retention_days)) * 1000
        )::BIGINT;

        IF tf_ms IS NULL THEN
            cutoff_ts := retention_cutoff_ts;
        ELSE
            min_keep_ts := (
                EXTRACT(EPOCH FROM NOW()) * 1000
            )::BIGINT - (tf_ms * 500);
            cutoff_ts := LEAST(retention_cutoff_ts, min_keep_ts);
        END IF;

        started_at := clock_timestamp();

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
$$ LANGUAGE plpgsql
"""


async def migrate_retention_horizon_guard() -> None:
    """Clamp finite-retention cleanup outside the warm-up horizon.

    Rollback by re-applying the prior cleanup_old_swap_data() body from
    migrate_swap_ohlcv_retention_policy.py.
    """
    async with get_db_session() as session:
        try:
            await session.execute(text(RETENTION_HORIZON_GUARD_SQL))
            await session.commit()
            logger.info("swap_ohlcv_p retention horizon guard applied")
        except Exception:
            await session.rollback()
            raise
