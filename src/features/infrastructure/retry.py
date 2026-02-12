"""
Retry decorator with exponential backoff for infrastructure operations.

.. deprecated::
    This module is deprecated. Use `src.utils.retry` instead, which provides:
    - Integration with centralized settings (src/config/settings.py)
    - Jitter support to prevent thundering herd
    - Factory functions: get_db_retry(), get_api_retry()

    Migration example:
        # Old:
        from src.features.infrastructure.retry import database_retry
        @database_retry(max_attempts=3)

        # New:
        from src.utils.retry import get_db_retry
        @get_db_retry()
"""

import functools
import logging
import time
import warnings
from collections.abc import Callable
from typing import Any, TypeVar

from src.logging import get_logger

warnings.warn(
    "src.features.infrastructure.retry is deprecated. "
    "Use src.utils.retry instead (get_db_retry, get_api_retry).",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from tenacity import (
        after_log,
        before_sleep_log,
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    retry = None  # type: ignore


logger = get_logger("features.infrastructure.retry")

T = TypeVar("T")


def simple_retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    logger_instance: logging.Logger | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Simple retry decorator without external dependencies.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)
        exceptions: Tuple of exception types to catch and retry
        logger_instance: Logger for retry events

    Returns:
        Decorated function with retry logic

    Example:
        @simple_retry(max_attempts=3, backoff_factor=2.0, exceptions=(ConnectionError,))
        def unstable_operation():
            # operation that might fail
            pass
    """
    log = logger_instance or logger

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        log.info(
                            f"{func.__name__} succeeded on attempt {attempt}/{max_attempts}"
                        )
                    return result

                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        log.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    sleep_time = backoff_factor ** (attempt - 1)
                    log.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time)

            # Should never reach here, but for type safety
            if last_exception:
                raise last_exception
            # This should never be reached, but mypy needs a return
            raise RuntimeError("Retry exhausted without result")

        return wrapper

    return decorator


def database_retry(
    max_attempts: int = 3,
    wait_multiplier: int = 1,
    wait_max: int = 10,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator specifically for database operations.

    Uses tenacity if available, otherwise falls back to simple_retry.
    Catches common database exceptions.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        wait_multiplier: Multiplier for exponential wait (default: 1)
        wait_max: Maximum wait time in seconds (default: 10)

    Returns:
        Decorated function with retry logic

    Example:
        @database_retry(max_attempts=5)
        async def insert_data(conn, data):
            await conn.execute("INSERT ...")
    """
    # Common database exceptions to retry
    # Note: Add specific driver exceptions as needed
    db_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,  # Network errors
    )

    # Try to add asyncpg exceptions if available
    try:
        import asyncpg

        db_exceptions = (
            *db_exceptions,
            asyncpg.PostgresConnectionError,
            asyncpg.CannotConnectNowError,
            asyncpg.ConnectionDoesNotExistError,
            asyncpg.TooManyConnectionsError,
        )
    except ImportError:
        pass

    if TENACITY_AVAILABLE and retry is not None:
        # Use tenacity for more sophisticated retry logic
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=wait_multiplier,
                max=wait_max,
            ),
            retry=retry_if_exception_type(db_exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )
    # Fallback to simple retry
    return simple_retry(
        max_attempts=max_attempts,
        backoff_factor=wait_multiplier,
        exceptions=db_exceptions,
    )


def api_retry(
    max_attempts: int = 5,
    wait_multiplier: int = 1,
    wait_max: int = 30,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Retry decorator for external API calls.

    Uses tenacity if available, with longer backoff for rate limiting.

    Args:
        max_attempts: Maximum number of retry attempts (default: 5)
        wait_multiplier: Multiplier for exponential wait (default: 1)
        wait_max: Maximum wait time in seconds (default: 30)

    Returns:
        Decorated function with retry logic

    Example:
        @api_retry(max_attempts=5, wait_max=30)
        def fetch_market_data(symbol):
            response = requests.get(f"https://api.../v1/{symbol}")
            return response.json()
    """
    api_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )

    # Try to add HTTP exceptions if requests is available
    try:
        import requests  # type: ignore[import-untyped]

        api_exceptions = (
            *api_exceptions,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        )
    except ImportError:
        pass

    if TENACITY_AVAILABLE and retry is not None:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=wait_multiplier,
                max=wait_max,
            ),
            retry=retry_if_exception_type(api_exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )
    return simple_retry(
        max_attempts=max_attempts,
        backoff_factor=wait_multiplier,
        exceptions=api_exceptions,
    )


# Convenience aliases
retry_on_db_error = database_retry
retry_on_api_error = api_retry


if not TENACITY_AVAILABLE:
    logger.warning(
        "tenacity library not installed. Using simple retry implementation. "
        "Install tenacity for advanced retry features: pip install tenacity"
    )
