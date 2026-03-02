import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def _unix(dt: datetime) -> int:
    return int(dt.replace(tzinfo=UTC).timestamp())


async def _create_parent(session) -> None:
    # Parent table partitioned by RANGE on integer timestamp (unix seconds)
    await session.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS ohlcv_p (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp BIGINT NOT NULL,
            open NUMERIC,
            high NUMERIC,
            low NUMERIC,
            close NUMERIC,
            volume NUMERIC,
            volccy NUMERIC,
            volusd NUMERIC
        ) PARTITION BY RANGE (timestamp);
        """
        )
    )

    # Common index on parent for planner (optional in PG)
    # child partitions will have their own local indexes


async def _create_daily_partition(session, day_start_ts: int, day_end_ts: int) -> None:
    name = f"ohlcv_p_{day_start_ts}_{day_end_ts}"
    await session.execute(
        text(
            f"""
        CREATE TABLE IF NOT EXISTS {name}
        PARTITION OF ohlcv_p FOR VALUES FROM ({day_start_ts}) TO ({day_end_ts});
        """
        )
    )
    # Local composite index
    await session.execute(
        text(
            f"""
        CREATE INDEX IF NOT EXISTS idx_{name}_sym_tf_ts
        ON {name}(symbol, timeframe, timestamp);
        """
        )
    )
    # BRIN on timestamp to speed range scans
    await session.execute(
        text(
            f"""
        CREATE INDEX IF NOT EXISTS brin_{name}_ts
        ON {name} USING BRIN (timestamp);
        """
        )
    )


async def migrate_create_ohlcv_partitioned() -> None:
    """
    Create partitioned ohlcv table and prepare recent partitions (last 90 days + next 7 days).
    """
    async with get_db_session() as session:
        await _create_parent(session)

        # Generate daily partitions
        today = datetime.now(UTC).date()
        start_date = today - timedelta(days=90)
        end_date = today + timedelta(days=7)

        cur = start_date
        created = 0
        while cur < end_date:
            day_start = datetime(cur.year, cur.month, cur.day, tzinfo=UTC)
            day_end = day_start + timedelta(days=1)
            await _create_daily_partition(session, _unix(day_start), _unix(day_end))
            created += 1
            cur += timedelta(days=1)

        await session.commit()
        logger.info(f"✅ ohlcv_p создана, подготовлено партиций: {created}")
