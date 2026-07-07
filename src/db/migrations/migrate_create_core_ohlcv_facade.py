"""Migration 540: create DB-side OHLCV facade for BI/SQL (§15.6).

Adds a read-only, PIT-aware function `core.f_ohlcv_pit(...)` and a
`security_barrier` view `core.v_ohlcv_facade` that mirror the semantics of the
code facade in `src.identity.application.ohlcv_facade.OhlcvFacade` /
`src.identity.infrastructure.ohlcv_facade_repository.SqlOhlcvFacadeRepository`:

- trivial series passthrough `public.swap_ohlcv_p` unchanged (`bar_kind='native'`,
  `adjustment_factor=1`, `succession_id=NULL`);
- composite series (series_kind='composite' in `core.series_registry`) read from
  the materialized `core.continuous_ohlcv_p` instead of raw;
- PIT alias resolution via `core.series_alias` (`old_series_id -> canonical_series_id`);
- PIT adjustment factor applied to OHLC (not volume) from `core.series_adjustments`,
  as-of the requested timestamp (default `now()`);
- output-only gap markers (`bar_kind='gap_marker'`, `is_gap=true`) from
  `core.series_gap_ranges`, never physically stored.

`core.v_ohlcv_facade` is defined in terms of `core.f_ohlcv_pit` (current
analytics snapshot, `as_of=NULL` => `now()`, gap markers always included) so the
view and the function cannot drift apart, and both stay aligned with the code
facade by construction of the shared SQL logic below.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

CORE_OHLCV_FACADE_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS core",
    """
CREATE OR REPLACE FUNCTION core.f_ohlcv_pit(
    p_series_id text,
    p_timeframe text,
    p_start_ts bigint,
    p_end_ts bigint,
    p_as_of timestamptz DEFAULT NULL,
    p_include_gap_markers boolean DEFAULT false
)
RETURNS TABLE (
    series_id text,
    timeframe text,
    timestamp bigint,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    volume numeric,
    segment_id text,
    source_venue text,
    source_symbol text,
    source_timestamp bigint,
    bar_kind text,
    data_status text,
    succession_id text,
    adjustment_factor numeric,
    is_gap boolean,
    gap_type text
)
LANGUAGE plpgsql
STABLE
AS $f_ohlcv_pit$
DECLARE
    v_as_of timestamptz := COALESCE(p_as_of, now());
    v_canonical_series_id text;
    v_series_kind text;
BEGIN
    SELECT a.canonical_series_id INTO v_canonical_series_id
    FROM core.series_alias a
    WHERE a.old_series_id = p_series_id
      AND a.known_from <= v_as_of
      AND (a.known_to IS NULL OR a.known_to > v_as_of)
    ORDER BY a.known_from DESC
    LIMIT 1;

    v_canonical_series_id := COALESCE(v_canonical_series_id, p_series_id);

    SELECT r.series_kind INTO v_series_kind
    FROM core.series_registry r
    WHERE r.series_id = v_canonical_series_id
    LIMIT 1;

    v_series_kind := COALESCE(v_series_kind, 'trivial');

    RETURN QUERY
    WITH base_rows AS (
        SELECT
            o.symbol AS series_id,
            o.timeframe,
            o.timestamp,
            o.open,
            o.high,
            o.low,
            o.close,
            o.volume,
            ('raw:' || o.symbol || ':' || o.timeframe) AS segment_id,
            'OKX'::text AS source_venue,
            o.symbol AS source_symbol,
            o.timestamp AS source_timestamp,
            'native'::text AS bar_kind,
            'complete'::text AS data_status,
            NULL::text AS succession_id,
            false AS is_gap,
            NULL::text AS gap_type
        FROM public.swap_ohlcv_p o
        WHERE v_series_kind <> 'composite'
          AND o.symbol = v_canonical_series_id
          AND o.timeframe = p_timeframe
          AND o.timestamp >= p_start_ts
          AND o.timestamp < p_end_ts

        UNION ALL

        SELECT
            c.series_id,
            c.timeframe,
            c.timestamp,
            c.open,
            c.high,
            c.low,
            c.close,
            c.volume,
            c.segment_id,
            c.source_venue,
            c.source_symbol,
            c.source_timestamp,
            c.bar_kind,
            c.data_status,
            c.succession_id,
            false AS is_gap,
            NULL::text AS gap_type
        FROM core.continuous_ohlcv_p c
        WHERE v_series_kind = 'composite'
          AND c.series_id = v_canonical_series_id
          AND c.timeframe = p_timeframe
          AND c.timestamp >= p_start_ts
          AND c.timestamp < p_end_ts
    ),
    gap_rows AS (
        SELECT
            g.series_id,
            p_timeframe AS timeframe,
            GREATEST(g.gap_start_ts, p_start_ts) AS timestamp,
            NULL::numeric AS open,
            NULL::numeric AS high,
            NULL::numeric AS low,
            NULL::numeric AS close,
            NULL::numeric AS volume,
            ('gap:' || g.series_id || ':' || p_timeframe || ':' || g.gap_start_ts)
                AS segment_id,
            NULL::text AS source_venue,
            NULL::text AS source_symbol,
            NULL::bigint AS source_timestamp,
            'gap_marker'::text AS bar_kind,
            'missing'::text AS data_status,
            NULL::text AS succession_id,
            true AS is_gap,
            g.gap_type
        FROM core.series_gap_ranges g
        WHERE p_include_gap_markers
          AND g.series_id = v_canonical_series_id
          AND (g.timeframe = p_timeframe OR g.timeframe = '*')
          AND g.gap_start_ts < p_end_ts
          AND g.gap_end_ts > p_start_ts
          AND g.known_from <= v_as_of
          AND (g.known_to IS NULL OR g.known_to > v_as_of)
    ),
    combined AS (
        SELECT * FROM base_rows
        UNION ALL
        SELECT * FROM gap_rows
    )
    SELECT
        r.series_id,
        r.timeframe,
        r.timestamp,
        CASE WHEN r.is_gap THEN NULL ELSE r.open * adj.factor END,
        CASE WHEN r.is_gap THEN NULL ELSE r.high * adj.factor END,
        CASE WHEN r.is_gap THEN NULL ELSE r.low * adj.factor END,
        CASE WHEN r.is_gap THEN NULL ELSE r.close * adj.factor END,
        r.volume,
        r.segment_id,
        r.source_venue,
        r.source_symbol,
        r.source_timestamp,
        r.bar_kind,
        r.data_status,
        r.succession_id,
        adj.factor,
        r.is_gap,
        r.gap_type
    FROM combined r
    CROSS JOIN LATERAL (
        SELECT COALESCE(
            (
                SELECT a.adjustment_factor
                FROM core.series_adjustments a
                WHERE a.series_id = r.series_id
                  AND a.effective_ts <= r.timestamp
                  AND a.known_from <= v_as_of
                  AND (a.known_to IS NULL OR a.known_to > v_as_of)
                ORDER BY a.effective_ts DESC, a.known_from DESC
                LIMIT 1
            ),
            1
        ) AS factor
    ) adj
    ORDER BY r.timestamp, r.is_gap DESC;
END;
$f_ohlcv_pit$
    """.strip(),
    """
CREATE OR REPLACE VIEW core.v_ohlcv_facade
WITH (security_barrier = true) AS
SELECT facade.*
FROM (
    SELECT DISTINCT o.symbol AS series_id, o.timeframe
    FROM public.swap_ohlcv_p o
    WHERE NOT EXISTS (
        SELECT 1
        FROM core.series_registry r
        WHERE r.series_id = o.symbol
          AND r.series_kind = 'composite'
    )

    UNION

    SELECT DISTINCT c.series_id, c.timeframe
    FROM core.continuous_ohlcv_p c
) keys
CROSS JOIN LATERAL core.f_ohlcv_pit(
    keys.series_id,
    keys.timeframe,
    0::bigint,
    9999999999999999::bigint,
    NULL::timestamptz,
    true
) AS facade
    """.strip(),
    """
COMMENT ON FUNCTION core.f_ohlcv_pit(text, text, bigint, bigint, timestamptz, boolean)
IS 'PIT/backtest OHLCV read facade for BI/SQL (§15.6); mirrors '
   'src.identity.application.ohlcv_facade.OhlcvFacade semantics.'
    """.strip(),
    """
COMMENT ON VIEW core.v_ohlcv_facade
IS 'Current-analytics OHLCV facade for BI/SQL (§15.6): passthrough trivial series '
   'union materialized composite series, with lineage/segment/gap columns. '
   'Analytical consumers must read this view, not public.swap_ohlcv_p or '
   'core.continuous_ohlcv_p directly (§12.3).'
    """.strip(),
)

CORE_OHLCV_FACADE_SQL = ";\n\n".join(CORE_OHLCV_FACADE_STATEMENTS) + ";"


async def migrate_create_core_ohlcv_facade() -> None:
    """Create core.f_ohlcv_pit(...) and core.v_ohlcv_facade for BI/SQL access."""
    async with get_db_session() as session:
        try:
            for statement in CORE_OHLCV_FACADE_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("core OHLCV facade (view + PIT function) ensured")
        except Exception:
            await session.rollback()
            raise
