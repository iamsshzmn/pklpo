"""
Migration: Phase 3 Quant Stack — расширение схемы БД.

Изменения:
1. ohlcv_p: добавление quant-колонок для dollar bars (bars_mode, bars_source,
   turnover, volume_unit, ts_start, ts_end, duration_s, trades_count).
   При bars_mode='time' (по умолчанию) новые колонки = NULL.

2. labels: новая таблица для triple-barrier меток.

3. ml_artifacts: новая таблица для артефактов ML pipeline.

Rollback: src/db/rollback_phase3_quant_tables.sql
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_engine

logger = logging.getLogger(__name__)


async def migrate_phase3_quant_tables() -> None:
    """Применить миграцию Phase 3 Quant Stack."""
    engine = get_async_engine()

    async with AsyncSession(engine) as session:

        # ------------------------------------------------------------------ #
        # 1. Расширение таблицы ohlcv_p для dollar bars                       #
        # ------------------------------------------------------------------ #
        await session.execute(text("""
            ALTER TABLE ohlcv_p
                ADD COLUMN IF NOT EXISTS bars_mode   VARCHAR(10)  DEFAULT 'time',
                ADD COLUMN IF NOT EXISTS bars_source VARCHAR(20),
                ADD COLUMN IF NOT EXISTS turnover    DOUBLE PRECISION,
                ADD COLUMN IF NOT EXISTS volume_unit VARCHAR(20),
                ADD COLUMN IF NOT EXISTS ts_start    BIGINT,
                ADD COLUMN IF NOT EXISTS ts_end      BIGINT,
                ADD COLUMN IF NOT EXISTS duration_s  INTEGER,
                ADD COLUMN IF NOT EXISTS trades_count INTEGER
        """))
        logger.info("Expanded ohlcv_p with quant columns (bars_mode, bars_source, ...)")

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ohlcv_p_bars_mode
                ON ohlcv_p (bars_mode)
                WHERE bars_mode = 'dollar'
        """))
        logger.info("Created partial index idx_ohlcv_p_bars_mode")

        # ------------------------------------------------------------------ #
        # 2. Таблица labels (triple-barrier)                                   #
        # ------------------------------------------------------------------ #
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS labels (
                id            BIGSERIAL PRIMARY KEY,
                symbol        VARCHAR(50)  NOT NULL,
                timeframe     VARCHAR(10)  NOT NULL,
                timestamp     BIGINT       NOT NULL,
                label         SMALLINT     NOT NULL CHECK (label IN (-1, 0, 1)),
                t1            BIGINT,
                barrier_type  VARCHAR(10)  CHECK (barrier_type IN ('pt', 'sl', 'vert')),
                pt            DOUBLE PRECISION,
                sl            DOUBLE PRECISION,
                max_h         INTEGER,
                run_id        VARCHAR(64)  NOT NULL,
                created_at    TIMESTAMPTZ  DEFAULT NOW()
            )
        """))
        logger.info("Created table: labels")

        await session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_labels_sym_tf_ts_run
                ON labels (symbol, timeframe, timestamp, run_id)
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_labels_run_id
                ON labels (run_id)
        """))

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_labels_sym_tf_ts
                ON labels (symbol, timeframe, timestamp)
        """))
        logger.info("Created indexes on labels")

        # ------------------------------------------------------------------ #
        # 3. Таблица ml_artifacts                                              #
        # ------------------------------------------------------------------ #
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_artifacts (
                id             BIGSERIAL    PRIMARY KEY,
                run_id         VARCHAR(64)  NOT NULL,
                artifact_type  VARCHAR(50)  NOT NULL,
                algo_version   VARCHAR(50)  NOT NULL,
                params_hash    VARCHAR(64)  NOT NULL,
                artifact_path  TEXT         NOT NULL,
                metrics        JSONB,
                created_at     TIMESTAMPTZ  DEFAULT NOW()
            )
        """))
        logger.info("Created table: ml_artifacts")

        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ml_artifacts_run
                ON ml_artifacts (run_id)
        """))

        await session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ml_artifacts_run_type
                ON ml_artifacts (run_id, artifact_type)
        """))
        logger.info("Created indexes on ml_artifacts")

        await session.commit()
        logger.info("Phase 3 Quant Stack migration completed successfully")


if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    asyncio.run(migrate_phase3_quant_tables())
