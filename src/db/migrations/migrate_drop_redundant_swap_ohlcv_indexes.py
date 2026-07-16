from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

REDUNDANT_SWAP_OHLCV_INDEXES = (
    "idx_swap_ohlcv_p_symbol_timeframe_timestamp",
    "idx_swap_ohlcv_p_lookup",
)

VALIDATE_REDUNDANT_SWAP_OHLCV_INDEXES_SQL = """
DO $$
DECLARE
    valid_indexes TEXT[] := ARRAY[
        'idx_swap_ohlcv_p_symbol_timeframe_timestamp',
        'idx_swap_ohlcv_p_lookup'
    ];
    bad_indexes TEXT[];
BEGIN
    SELECT array_agg(c.relname ORDER BY c.relname)
    INTO bad_indexes
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_index i ON i.indexrelid = c.oid
    JOIN pg_class t ON t.oid = i.indrelid
    WHERE n.nspname = 'public'
      AND t.relname = 'swap_ohlcv_p'
      AND c.relname = ANY(valid_indexes)
      AND NOT (
          i.indisprimary IS FALSE
          AND i.indnkeyatts = 3
          AND i.indnatts = 3
          AND i.indpred IS NULL
          AND i.indexprs IS NULL
          AND ARRAY(
              SELECT a.attname::text
              FROM unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
              JOIN pg_attribute a
                ON a.attrelid = i.indrelid
               AND a.attnum = k.attnum
              ORDER BY k.ord
          ) = ARRAY['symbol', 'timeframe', 'timestamp']
      );

    IF bad_indexes IS NOT NULL THEN
        RAISE EXCEPTION
            'Refusing to drop swap_ohlcv_p index(es) with unexpected definition: %',
            bad_indexes;
    END IF;
END
$$
"""

DROP_REDUNDANT_SWAP_OHLCV_INDEXES_STATEMENTS = (
    VALIDATE_REDUNDANT_SWAP_OHLCV_INDEXES_SQL,
    "DROP INDEX IF EXISTS idx_swap_ohlcv_p_symbol_timeframe_timestamp",
    "DROP INDEX IF EXISTS idx_swap_ohlcv_p_lookup",
)

DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL = ";\n\n".join(
    DROP_REDUNDANT_SWAP_OHLCV_INDEXES_STATEMENTS
)


async def migrate_drop_redundant_swap_ohlcv_indexes() -> None:
    """Drop non-PK indexes duplicating swap_ohlcv_p(symbol,timeframe,timestamp).

    The migration verifies the target indexes are plain, non-primary, three-column
    btree indexes before dropping them. Rollback:

        CREATE INDEX idx_swap_ohlcv_p_symbol_timeframe_timestamp
            ON swap_ohlcv_p (symbol, timeframe, timestamp);
        CREATE INDEX idx_swap_ohlcv_p_lookup
            ON swap_ohlcv_p (symbol, timeframe, timestamp);
    """
    async with get_db_session() as session:
        try:
            for statement in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("redundant swap_ohlcv_p lookup indexes dropped")
        except Exception:
            await session.rollback()
            raise
