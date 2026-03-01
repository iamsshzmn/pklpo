"""
UPSERT execution with retry logic.

Wraps the build_and_execute_upsert function with exponential backoff retry
for transient database errors.

Extracted from inserter.py (Stage 2 refactoring).
"""

import asyncio
from typing import Any

from sqlalchemy.exc import DBAPIError, OperationalError

from src.logging import get_logger

from ..upsert_builder import build_and_execute_upsert

logger = get_logger(__name__)

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0

# Exceptions that warrant a retry
RETRYABLE_EXCEPTIONS = (
    OperationalError,
    DBAPIError,
    ConnectionError,
    TimeoutError,
)


async def execute_upsert_with_retry(
    session,
    indicators_table,
    records: list[dict[str, Any]],
    db_columns: set[str],
    pk: tuple[str, ...],
    required_fields: set[str],
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> int:
    """
    Execute UPSERT with exponential backoff retry.

    Args:
        session: SQLAlchemy async session
        indicators_table: Reflected SQLAlchemy table
        records: List of record dictionaries to upsert
        db_columns: Set of column names in the database
        pk: Primary key column names
        required_fields: Set of required field names
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry

    Returns:
        Number of records saved

    Raises:
        Exception: If all retries exhausted
    """
    if not records:
        return 0

    last_exception = None
    delay = base_delay

    for attempt in range(max_retries + 1):
        try:
            return await build_and_execute_upsert(
                session=session,
                model_class=indicators_table,
                records=records,
                db_cols=db_columns,
                pk=pk,
                required_fields=required_fields,
            )

        except RETRYABLE_EXCEPTIONS as e:
            last_exception = e

            if attempt < max_retries:
                logger.warning(
                    f"UPSERT retry {attempt + 1}/{max_retries} after error: {e}. "
                    f"Waiting {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(
                    f"UPSERT failed after {max_retries} retries. Last error: {e}"
                )

    raise last_exception  # type: ignore[misc]


async def check_db_state_before_after(
    session,
    symbol: str,
    timeframe: str,
    check_db_state_func,
) -> tuple[int | None, int | None]:
    """
    Check database state for diagnostics.

    Args:
        session: SQLAlchemy async session
        symbol: Trading symbol
        timeframe: Timeframe
        check_db_state_func: Async function to check DB state

    Returns:
        Tuple of (row_count, max_timestamp) or (None, None) on error
    """
    try:
        result = await check_db_state_func(session, symbol, timeframe)
        # Explicitly unpack to satisfy type checker
        count, ts = result
        return (int(count) if count is not None else None,
                int(ts) if ts is not None else None)
    except Exception as e:
        logger.warning(f"Failed to check DB state: {e}")
        return None, None
