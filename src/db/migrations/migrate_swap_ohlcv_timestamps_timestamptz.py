import logging
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database import DATABASE_URL, connect_args

logger = logging.getLogger(__name__)

TIMESTAMP_COLUMNS = ("fetched_at", "created_at")
PARENT_TABLE_NAME = "swap_ohlcv_p"


def _build_alter_timestamp_type_sql(table_ref: str, column_name: str) -> str:
    return f"""
    ALTER TABLE {table_ref}
    ALTER COLUMN {column_name}
    TYPE TIMESTAMPTZ
    USING {column_name} AT TIME ZONE 'UTC'
    """


def _build_set_default_now_sql(table_ref: str, column_name: str) -> str:
    return f"""
    ALTER TABLE {table_ref}
    ALTER COLUMN {column_name}
    SET DEFAULT NOW()
    """


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


async def _column_is_timestamptz(session, table_name: str, column_name: str) -> bool:
    res = await session.execute(
        text(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    row = res.fetchone()
    return bool(row and row[0] == "timestamp with time zone")


async def _list_partition_relations(session) -> list[str]:
    res = await session.execute(
        text(
            """
            SELECT relid::regclass::text
            FROM pg_partition_tree('public.swap_ohlcv_p'::regclass)
            WHERE relid::regclass::text <> 'swap_ohlcv_p'
            ORDER BY level, relid::regclass::text
            """
        )
    )
    return [str(row[0]) for row in res.fetchall()]


@asynccontextmanager
async def _get_migration_session() -> AsyncSession:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_size=1,
        max_overflow=0,
        connect_args={**connect_args, "command_timeout": 300},
    )
    session_factory = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()


async def migrate_swap_ohlcv_timestamps_timestamptz() -> None:
    async with _get_migration_session() as session:
        try:
            if not await _table_exists(session, PARENT_TABLE_NAME):
                logger.info(
                    "swap_ohlcv_p is absent; skipping timestamptz normalization"
                )
                return

            partition_relations: list[str] = []
            if await _is_partitioned_table(session, PARENT_TABLE_NAME):
                partition_relations = await _list_partition_relations(session)

            for column_name in TIMESTAMP_COLUMNS:
                if not await _column_is_timestamptz(
                    session, PARENT_TABLE_NAME, column_name
                ):
                    await session.execute(
                        text(
                            _build_alter_timestamp_type_sql(
                                PARENT_TABLE_NAME, column_name
                            )
                        )
                    )
                    await session.commit()

                for table_ref in [PARENT_TABLE_NAME, *partition_relations]:
                    await session.execute(
                        text(_build_set_default_now_sql(table_ref, column_name))
                    )
                await session.commit()

            logger.info("swap_ohlcv_p timestamp columns normalized to timestamptz")
        except Exception:
            await session.rollback()
            raise
