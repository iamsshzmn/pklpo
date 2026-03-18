import logging
from datetime import UTC, date, datetime

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=UTC)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    absolute = year * 12 + (month - 1) + delta
    return absolute // 12, absolute % 12 + 1


def _month_partition_name(prefix: str, dt: datetime) -> str:
    return f"{prefix}_{dt.year:04d}_{dt.month:02d}"


async def _table_exists(session, table_name: str) -> bool:
    res = await session.execute(
        text("SELECT to_regclass(:table_name) IS NOT NULL"),
        {"table_name": table_name},
    )
    return bool(res.scalar())


async def _is_partitioned_table(session, table_name: str) -> bool:
    res = await session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_partitioned_table pt
                JOIN pg_class c ON c.oid = pt.partrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return bool(res.scalar())


async def _create_parent_table(session) -> None:
    await session.execute(
        text(
            """
            CREATE TABLE swap_ohlcv_p (
                symbol VARCHAR(50) NOT NULL,
                timeframe VARCHAR(20) NOT NULL,
                timestamp BIGINT NOT NULL,
                open DECIMAL(20,8) NOT NULL,
                high DECIMAL(20,8) NOT NULL,
                low DECIMAL(20,8) NOT NULL,
                close DECIMAL(20,8) NOT NULL,
                volume DECIMAL(30,8) NOT NULL,
                vol_ccy DECIMAL(30,8),
                vol_usd DECIMAL(30,8),
                funding_rate DECIMAL(10,8),
                open_interest DECIMAL(30,8),
                fetched_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (symbol, timeframe, timestamp)
            ) PARTITION BY RANGE (timestamp);
            """
        )
    )

    await session.execute(
        text(
            """
            CREATE INDEX idx_swap_ohlcv_p_symbol_timeframe_timestamp
            ON swap_ohlcv_p (symbol, timeframe, timestamp);
            """
        )
    )

    await session.execute(
        text(
            """
            CREATE INDEX idx_swap_ohlcv_p_lookup
            ON swap_ohlcv_p (symbol, timeframe, timestamp);
            """
        )
    )


async def _create_monthly_partitions(session, months_back: int = 2, months_forward: int = 6) -> None:
    today = date.today()
    base = _month_start(today.year, today.month)

    for delta in range(-months_back, months_forward + 1):
        start_year, start_month = _add_months(base.year, base.month, delta)
        end_year, end_month = _add_months(base.year, base.month, delta + 1)
        start_dt = _month_start(start_year, start_month)
        end_dt = _month_start(end_year, end_month)
        partition_name = _month_partition_name("swap_ohlcv_p", start_dt)

        await session.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF swap_ohlcv_p
                FOR VALUES FROM ({int(start_dt.timestamp() * 1000)}) TO ({int(end_dt.timestamp() * 1000)});
                """
            )
        )

    await session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS swap_ohlcv_p_default
            PARTITION OF swap_ohlcv_p DEFAULT;
            """
        )
    )


async def _recreate_cleanup_trigger_if_possible(session) -> None:
    res = await session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname = 'trigger_cleanup_old_data'
            )
            """
        )
    )
    trigger_function_exists = bool(res.scalar())
    if not trigger_function_exists:
        logger.info(
            "skip recreating trigger_cleanup_swap_data: trigger_cleanup_old_data() is absent"
        )
        return

    await session.execute(
        text(
            """
            DROP TRIGGER IF EXISTS trigger_cleanup_swap_data ON swap_ohlcv_p;

            CREATE TRIGGER trigger_cleanup_swap_data
            AFTER INSERT ON swap_ohlcv_p
            FOR EACH ROW
            EXECUTE FUNCTION trigger_cleanup_old_data();
            """
        )
    )


async def migrate_recreate_swap_ohlcv_partitioned() -> None:
    """
    Recreate swap_ohlcv_p as a partitioned parent table.

    Existing rows are intentionally discarded. The table is recreated with a
    monthly partition layout and a default partition to avoid insert failures
    outside the bootstrap range.
    """
    async with get_db_session() as session:
        try:
            if await _is_partitioned_table(session, "swap_ohlcv_p"):
                logger.info(
                    "swap_ohlcv_p is already partitioned; ensuring partitions and trigger"
                )
                await _create_monthly_partitions(session)
                await _recreate_cleanup_trigger_if_possible(session)
                await session.commit()
                return

            if await _table_exists(session, "swap_ohlcv_p"):
                logger.warning(
                    "recreating swap_ohlcv_p as partitioned parent; existing rows will be dropped"
                )
                await session.execute(text("DROP TABLE swap_ohlcv_p CASCADE"))

            await _create_parent_table(session)
            await _create_monthly_partitions(session)
            await _recreate_cleanup_trigger_if_possible(session)

            await session.commit()
            logger.info("swap_ohlcv_p recreated as partitioned parent")
        except Exception:
            await session.rollback()
            raise
