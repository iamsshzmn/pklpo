"""
Schema checking functions for database schema validation.
"""

from typing import Any

from sqlalchemy import MetaData, Table, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logging import (
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)

from ...storage_contract import IndicatorStorageContract

logger = get_category_logger(LogCategory.SCHEMA)


async def check_unique_index(session: AsyncSession) -> None:
    """
    Check that unique index on (symbol, timeframe, timestamp) exists.

    Args:
        session: Async database session
    """
    # Only run diagnostics in DEBUG mode
    if not should_log(LogCategory.DIAG, Verbosity.DEBUG):
        return

    logger.debug("Checking unique index...")
    try:
        index_query = text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = :table_name
            AND indexdef LIKE '%UNIQUE%'
        """
        )
        result = await session.execute(
            index_query,
            {"table_name": IndicatorStorageContract.table_name},
        )
        indexes = [row[0] for row in result.all()]

        #
        has_correct_index = any(
            "symbol" in idx and "timeframe" in idx and "timestamp" in idx
            for idx in indexes
        )
        if not has_correct_index:
            logger.error("No unique index on (symbol, timeframe, timestamp) found!")
        else:
            logger.debug(f"Unique indexes found: {len(indexes)}")

    except Exception as e:
        logger.error(f"Failed to check indexes: {e}")


async def check_schema_and_search_path(session: AsyncSession) -> None:
    """
    Check database schema and search_path.

    Args:
        session: Async database session
    """
    # Only run diagnostics in DEBUG mode
    if not should_log(LogCategory.DIAG, Verbosity.DEBUG):
        return

    try:
        schema_query = text(
            """
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_name = :table_name
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """
        )
        result = await session.execute(
            schema_query, {"table_name": IndicatorStorageContract.table_name}
        )
        columns = result.all()

        logger.debug(
            "public.%s: %d columns",
            IndicatorStorageContract.table_name,
            len(columns),
        )

    except Exception as e:
        logger.error(f"Failed to check schema: {e}")


async def load_db_columns(session: AsyncSession) -> set[str]:
    """
    Load database column names from information_schema.

    Args:
        session: Async database session

    Returns:
        Set of database column names
    """
    result = await session.execute(
        text(
            """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND table_schema = 'public'
    """
        ),
        {"table_name": IndicatorStorageContract.table_name},
    )
    db_cols = {row[0] for row in result.all()}
    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"DB schema: {len(db_cols)} columns")
    return db_cols


async def reflect_indicators_table(session: AsyncSession) -> Table:
    """
    Reflect indicators table from database.

    Args:
        session: Async database session

    Returns:
        Reflected Table object
    """
    metadata = MetaData()

    #  run_sync    reflection  async
    from sqlalchemy import inspect

    if session.bind is None:
        raise ValueError("Session bind is None, cannot reflect table")

    #  sync_engine  connection.run_sync
    def _reflect_table(sync_conn):
        """reflection   async ."""
        insp = inspect(sync_conn)
        columns = insp.get_columns(
            IndicatorStorageContract.table_name,
            schema="public",
        )

        #
        table = Table(
            IndicatorStorageContract.table_name,
            metadata,
            schema="public",
        )

        #
        for col_info in columns:
            from sqlalchemy import Column
            from sqlalchemy.types import (
                BigInteger,
                DateTime,
                Numeric,
                String,
            )

            #
            col_type_str = str(col_info["type"]).upper()
            if "VARCHAR" in col_type_str:
                col_type = String(col_info.get("length"))
            elif "NUMERIC" in col_type_str or "DECIMAL" in col_type_str:
                col_type = Numeric(
                    precision=col_info.get("precision"),
                    scale=col_info.get("scale"),
                )
            elif "DOUBLE PRECISION" in col_type_str or "FLOAT8" in col_type_str:
                from sqlalchemy.types import Float

                col_type = Float()
            elif "REAL" in col_type_str or "FLOAT4" in col_type_str:
                from sqlalchemy.types import REAL

                col_type = REAL()
            elif "BIGINT" in col_type_str:
                col_type = BigInteger()
            elif "INTEGER" in col_type_str or "INT" in col_type_str:
                from sqlalchemy.types import Integer

                col_type = Integer()
            elif "SMALLINT" in col_type_str:
                from sqlalchemy.types import SmallInteger

                col_type = SmallInteger()
            elif "TIMESTAMP" in col_type_str:
                col_type = DateTime()
            else:
                col_type = String()  # Fallback

            table.append_column(
                Column(
                    col_info["name"],
                    col_type,
                    nullable=col_info.get("nullable", True),
                )
            )

        return table

    #  connection   reflection  run_sync
    conn = await session.connection()
    indicators_table = await conn.run_sync(_reflect_table)

    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Table reflected: {len(indicators_table.columns)} columns")
    return indicators_table


async def check_db_state(
    session: AsyncSession, symbol: str, timeframe: str
) -> tuple[int | None, Any]:
    """
    Check database state before/after UPSERT.

    Args:
        session: Async database session
        symbol: Symbol to check
        timeframe: Timeframe to check

    Returns:
        Tuple of (count, max_timestamp)
    """
    try:
        count_query = text(
            f"""
            SELECT COUNT(*), MAX(timestamp)
            FROM public.{IndicatorStorageContract.table_name}
            WHERE symbol = :symbol AND timeframe = :timeframe
        """
        )
        result = await session.execute(
            count_query, {"symbol": symbol, "timeframe": timeframe}
        )
        row = result.fetchone()
        if row is None:
            return 0, None
        count, max_ts = row
        return count, max_ts
    except Exception as e:
        logger.error(f"Failed to check DB state: {e}")
        return 0, None
