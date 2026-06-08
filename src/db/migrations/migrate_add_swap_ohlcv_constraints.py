"""Add NOT VALID DB protection constraints to swap_ohlcv_p.

Rollback snippets:
    ALTER TABLE swap_ohlcv_p DROP CONSTRAINT chk_swap_ohlcv_p_timestamp_nonneg;
    ALTER TABLE swap_ohlcv_p DROP CONSTRAINT chk_swap_ohlcv_p_prices_positive;
    ALTER TABLE swap_ohlcv_p DROP CONSTRAINT chk_swap_ohlcv_p_volume_nonneg;
    ALTER TABLE swap_ohlcv_p DROP CONSTRAINT chk_swap_ohlcv_p_geometry;
    ALTER TABLE swap_ohlcv_p DROP CONSTRAINT chk_swap_ohlcv_p_timeframe_supported;
"""

from __future__ import annotations

from sqlalchemy import text

from src.utils.session_utils import get_db_session

SWAP_OHLCV_CONSTRAINTS: tuple[tuple[str, str], ...] = (
    (
        "chk_swap_ohlcv_p_timestamp_nonneg",
        "CHECK (timestamp >= 0) NOT VALID",
    ),
    (
        "chk_swap_ohlcv_p_prices_positive",
        "CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0) NOT VALID",
    ),
    (
        "chk_swap_ohlcv_p_volume_nonneg",
        "CHECK (volume >= 0) NOT VALID",
    ),
    (
        "chk_swap_ohlcv_p_geometry",
        """
        CHECK (
            high >= low
            AND high >= GREATEST(open, close)
            AND low <= LEAST(open, close)
        ) NOT VALID
        """,
    ),
    (
        "chk_swap_ohlcv_p_timeframe_supported",
        """
        CHECK (timeframe IN ('1m','5m','15m','30m','1H','4H','12H','1D','1W','1M'))
        NOT VALID
        """,
    ),
)


def _add_constraint_sql(name: str, check_sql: str) -> str:
    return f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = '{name}'
          AND conrelid = 'swap_ohlcv_p'::regclass
    ) THEN
        ALTER TABLE swap_ohlcv_p
            ADD CONSTRAINT {name}
            {check_sql};
    END IF;
END;
$$
"""


async def migrate_add_swap_ohlcv_constraints() -> None:
    """Idempotently add CHECK constraints to the partitioned swap OHLCV parent."""
    async with get_db_session() as session:
        try:
            for name, check_sql in SWAP_OHLCV_CONSTRAINTS:
                await session.execute(text(_add_constraint_sql(name, check_sql)))
            await session.commit()
        except Exception:
            await session.rollback()
            raise
