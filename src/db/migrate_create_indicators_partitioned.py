import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def _unix(dt: datetime) -> int:
    return int(dt.replace(tzinfo=UTC).timestamp())


async def _create_parent(session) -> None:
    await session.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS indicators_p (
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp BIGINT NOT NULL
            -- дополнительные столбцы индикаторов остаются как есть, вставляются при сохранении
        ) PARTITION BY RANGE (timestamp);
        """
        )
    )


async def _create_month_partition(
    session, month_start_ts: int, month_end_ts: int
) -> None:
    name = f"indicators_p_{month_start_ts}_{month_end_ts}"
    await session.execute(
        text(
            f"""
        CREATE TABLE IF NOT EXISTS {name}
        PARTITION OF indicators_p FOR VALUES FROM ({month_start_ts}) TO ({month_end_ts});
        """
        )
    )
    await session.execute(
        text(
            f"""
        CREATE INDEX IF NOT EXISTS idx_{name}_sym_tf_ts
        ON {name}(symbol, timeframe, timestamp);
        """
        )
    )
    await session.execute(
        text(
            f"""
        CREATE INDEX IF NOT EXISTS brin_{name}_ts
        ON {name} USING BRIN (timestamp);
        """
        )
    )


def _month_bounds(dt: datetime) -> (datetime, datetime):
    start = datetime(dt.year, dt.month, 1, tzinfo=UTC)
    if dt.month == 12:
        end = datetime(dt.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
    return start, end


async def migrate_create_indicators_partitioned() -> None:
    """
    Create partitioned indicators table and prepare monthly partitions
    (last 12 months + next month).
    """
    async with get_db_session() as session:
        await _create_parent(session)

        today = datetime.now(UTC)
        # last 12 months + next 1
        created = 0
        for back in range(12, -2, -1):
            ref = today - timedelta(days=back * 30)
            mstart, mend = _month_bounds(ref)
            await _create_month_partition(session, _unix(mstart), _unix(mend))
            created += 1

        await session.commit()
        logger.info(f"✅ indicators_p создана, подготовлено партиций: {created}")
