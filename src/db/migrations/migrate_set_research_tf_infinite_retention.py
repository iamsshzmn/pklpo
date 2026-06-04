from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

RESEARCH_TIMEFRAMES = ("1H", "4H", "1D")

RESEARCH_TF_INFINITE_RETENTION_SQL = """
UPDATE swap_ohlcv_retention_policy
SET retention_days = NULL,
    updated_at = NOW()
WHERE timeframe IN ('1H', '4H', '1D')
"""


async def migrate_set_research_tf_infinite_retention() -> None:
    """Set deep research timeframes to infinite retention.

    Rollback, if needed:

        UPDATE swap_ohlcv_retention_policy SET retention_days = 14 WHERE timeframe = '1H';
        UPDATE swap_ohlcv_retention_policy SET retention_days = 60 WHERE timeframe = '4H';
        UPDATE swap_ohlcv_retention_policy SET retention_days = 400 WHERE timeframe = '1D';
    """
    async with get_db_session() as session:
        try:
            await session.execute(text(RESEARCH_TF_INFINITE_RETENTION_SQL))
            await session.commit()
            logger.info("research timeframe retention set to infinite")
        except Exception:
            await session.rollback()
            raise
