import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_add_core_indexes() -> None:
    """
    Add core composite and BRIN indexes for large tables.
    Uses IF NOT EXISTS to be idempotent.
    """
    # Composite btree indexes
    idx_sql = [
        # ohlcv
        """
        CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_timeframe_ts
        ON ohlcv(symbol, timeframe, timestamp);
        """,
        # indicators
        """
        CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timeframe_ts
        ON indicators(symbol, timeframe, timestamp);
        """,
        # signals (если есть)
        """
        CREATE INDEX IF NOT EXISTS idx_signals_symbol_timeframe_ts
        ON signals(symbol, timeframe, timestamp);
        """,
    ]

    # BRIN indexes for timestamp columns to speed up range scans on large tables
    brin_sql = [
        """
        CREATE INDEX IF NOT EXISTS brin_ohlcv_ts
        ON ohlcv USING BRIN (timestamp);
        """,
        """
        CREATE INDEX IF NOT EXISTS brin_indicators_ts
        ON indicators USING BRIN (timestamp);
        """,
        """
        CREATE INDEX IF NOT EXISTS brin_signals_ts
        ON signals USING BRIN (timestamp);
        """,
    ]

    async with get_db_session() as session:
        for sql in idx_sql + brin_sql:
            try:
                await session.execute(text(sql))
            except Exception as e:
                # Не прерываем всю миграцию из-за отсутствующих таблиц
                logger.warning(f"⚠️ Индекс пропущен: {e}")
        await session.commit()
        logger.info("✅ Добавлены базовые индексы (btree+brin), где применимо")
