"""
Migration: recreate indicators_p with monthly naming (indicators_p_YYYY_MM).

Drops the existing indicators_p (with unix-timestamp partition names) and recreates
it with the same monthly partition convention used by swap_ohlcv_p.

Data loss: intentional — existing indicator data is recalculated by features_calc_short.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

PARENT_TABLE = "indicators_p"
MONTHS_BACK = 1
MONTHS_AHEAD = 6


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=UTC)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    absolute = year * 12 + (month - 1) + delta
    return absolute // 12, absolute % 12 + 1


def _partition_name(dt: datetime) -> str:
    return f"{PARENT_TABLE}_{dt.year:04d}_{dt.month:02d}"


def _unix_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


async def run(dry_run: bool = True) -> None:
    logger.info("migrate_recreate_indicators_partitioned dry_run=%s", dry_run)

    async with get_db_session() as session:
        # Drop existing indicators_p (cascade removes all child partitions)
        logger.info("Dropping %s CASCADE ...", PARENT_TABLE)
        if not dry_run:
            await session.execute(text(f"DROP TABLE IF EXISTS {PARENT_TABLE} CASCADE"))

        # Recreate parent
        logger.info("Creating %s parent ...", PARENT_TABLE)
        create_parent_sql = f"""
            CREATE TABLE {PARENT_TABLE} (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp BIGINT NOT NULL,
                calculated_at TIMESTAMPTZ,
                data_status VARCHAR(10) DEFAULT 'ok',
                failed_groups TEXT,
                cdl_doji SMALLINT,
                cdl_inside SMALLINT
            ) PARTITION BY RANGE (timestamp)
        """
        if not dry_run:
            await session.execute(text(create_parent_sql))

        # Primary key on parent
        pk_sql = f"""
            ALTER TABLE {PARENT_TABLE}
            ADD CONSTRAINT pk_indicators_p_symbol_timeframe_timestamp
            PRIMARY KEY (symbol, timeframe, timestamp)
        """
        if not dry_run:
            await session.execute(text(pk_sql))

        # Create monthly partitions
        now = datetime.now(UTC)
        year, month = now.year, now.month

        for delta in range(-MONTHS_BACK, MONTHS_AHEAD + 1):
            sy, sm = _add_months(year, month, delta)
            ey, em = _add_months(sy, sm, 1)
            start = _month_start(sy, sm)
            end = _month_start(ey, em)
            name = _partition_name(start)
            start_ts = _unix_ms(start)
            end_ts = _unix_ms(end)

            logger.info("  partition %s [%s, %s)", name, start_ts, end_ts)
            if not dry_run:
                await session.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {name}
                        PARTITION OF {PARENT_TABLE}
                        FOR VALUES FROM ({start_ts}) TO ({end_ts})
                        """
                    )
                )
                await session.execute(
                    text(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{name}_sym_tf_ts
                        ON {name}(symbol, timeframe, timestamp)
                        """
                    )
                )

        # Default partition for future overflow
        logger.info("  partition %s_default (DEFAULT)", PARENT_TABLE)
        if not dry_run:
            await session.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {PARENT_TABLE}_default
                    PARTITION OF {PARENT_TABLE} DEFAULT
                    """
                )
            )

        if not dry_run:
            await session.commit()
            logger.info("migrate_recreate_indicators_partitioned: done")
        else:
            logger.info("migrate_recreate_indicators_partitioned: dry-run complete, no changes made")
