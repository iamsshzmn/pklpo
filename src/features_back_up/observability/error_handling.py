"""
Enhanced error handling and logging for features module.

This module provides comprehensive error handling, retry mechanisms,
and detailed logging for features calculation and saving operations.
"""

import asyncio
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from .logging import get_features_logger

logger = get_features_logger("features.error_handling")


class FeaturesError(Exception):
    """Base exception for features module."""

    pass


class CalculationError(FeaturesError):
    """Exception for calculation errors."""

    pass


class DatabaseError(FeaturesError):
    """Exception for database errors."""

    pass


class ValidationError(FeaturesError):
    """Exception for validation errors."""

    pass


class RetryableError(FeaturesError):
    """Exception that can be retried."""

    pass


class ErrorHandler:
    """Comprehensive error handler for features operations."""

    def __init__(self):
        self.logger = get_features_logger("features.error_handling")
        self.error_counts = {}
        self.retry_config = {
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 60.0,
            "backoff_factor": 2.0,
        }

    def handle_calculation_error(
        self, error: Exception, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle calculation errors with detailed logging."""
        error_id = f"calc_{int(time.time())}"

        self.logger.error(f"Calculation error {error_id}: {error!s}")
        self.logger.error(f"Context: {context}")
        self.logger.error(f"Traceback: {traceback.format_exc()}")

        # Track error counts
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        return {
            "error_id": error_id,
            "error_type": error_type,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.now(UTC).isoformat(),
            "retryable": isinstance(error, RetryableError),
        }

    def handle_database_error(
        self, error: Exception, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle database errors with detailed logging."""
        error_id = f"db_{int(time.time())}"

        self.logger.error(f"Database error {error_id}: {error!s}")
        self.logger.error(f"Context: {context}")
        self.logger.error(f"Traceback: {traceback.format_exc()}")

        # Track error counts
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        return {
            "error_id": error_id,
            "error_type": error_type,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.now(UTC).isoformat(),
            "retryable": isinstance(error, RetryableError),
        }

    def handle_validation_error(
        self, error: Exception, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle validation errors with detailed logging."""
        error_id = f"val_{int(time.time())}"

        self.logger.error(f"Validation error {error_id}: {error!s}")
        self.logger.error(f"Context: {context}")

        return {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.now(UTC).isoformat(),
            "retryable": False,
        }

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of all errors encountered."""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts": self.error_counts.copy(),
            "timestamp": datetime.now(UTC).isoformat(),
        }


def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (RetryableError,),
):
    """
    Decorator for retrying operations on failure.

    Args:
        max_retries: Maximum number of retries
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry
        retryable_exceptions: Tuple of exception types that can be retried
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if this exception can be retried
                    if not isinstance(e, retryable_exceptions):
                        logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                        raise

                    if attempt == max_retries:
                        logger.error(f"Max retries exceeded for {func.__name__}: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor**attempt), max_delay)

                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)

            # This should never be reached
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if this exception can be retried
                    if not isinstance(e, retryable_exceptions):
                        logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                        raise

                    if attempt == max_retries:
                        logger.error(f"Max retries exceeded for {func.__name__}: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor**attempt), max_delay)

                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)

            # This should never be reached
            raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def log_operation_start(operation_name: str, context: dict[str, Any]) -> str:
    """Log the start of an operation."""
    operation_id = f"{operation_name}_{int(time.time())}"

    context_str = ", ".join(f"{k}={v}" for k, v in context.items())
    logger.info(
        f"Starting {operation_name}, operation_id={operation_id}, {context_str}"
    )

    return operation_id


def log_operation_success(
    operation_id: str, operation_name: str, duration: float, result: dict[str, Any]
) -> None:
    """Log successful completion of an operation."""
    logger.info(
        f"Completed {operation_name}",
        operation_id=operation_id,
        duration_seconds=duration,
        **result,
    )


def log_operation_failure(
    operation_id: str, operation_name: str, duration: float, error: Exception
) -> None:
    """Log failed completion of an operation."""
    logger.error(
        f"Failed {operation_name}",
        operation_id=operation_id,
        duration_seconds=duration,
        error=str(error),
        error_type=type(error).__name__,
    )


def safe_execute(func: Callable[..., Any], *args, **kwargs) -> dict[str, Any]:
    """
    Safely execute a function with comprehensive error handling.

    Args:
        func: Function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Dictionary with execution result
    """
    start_time = time.time()
    operation_id = log_operation_start(func.__name__, {"args_count": len(args)})

    try:
        result = func(*args, **kwargs)
        duration = time.time() - start_time

        log_operation_success(operation_id, func.__name__, duration, {"result": result})

        return {
            "success": True,
            "result": result,
            "operation_id": operation_id,
            "duration": duration,
        }

    except Exception as e:
        duration = time.time() - start_time

        log_operation_failure(operation_id, func.__name__, duration, e)

        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "operation_id": operation_id,
            "duration": duration,
        }


async def safe_execute_async(
    func: Callable[..., Any], *args, **kwargs
) -> dict[str, Any]:
    """
    Safely execute an async function with comprehensive error handling.

    Args:
        func: Async function to execute
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Dictionary with execution result
    """
    start_time = time.time()
    operation_id = log_operation_start(func.__name__, {"args_count": len(args)})

    try:
        result = await func(*args, **kwargs)
        duration = time.time() - start_time

        log_operation_success(operation_id, func.__name__, duration, {"result": result})

        return {
            "success": True,
            "result": result,
            "operation_id": operation_id,
            "duration": duration,
        }

    except Exception as e:
        duration = time.time() - start_time

        log_operation_failure(operation_id, func.__name__, duration, e)

        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "operation_id": operation_id,
            "duration": duration,
        }


class ErrorRecovery:
    """Error recovery strategies for different types of failures."""

    def __init__(self):
        self.logger = get_features_logger("features.error_recovery")

    def recover_from_calculation_failure(
        self, error: Exception, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Recover from calculation failures."""
        recovery_strategies = []

        if "insufficient data" in str(error).lower():
            recovery_strategies.append("Request more historical data")

        if "memory" in str(error).lower():
            recovery_strategies.append("Reduce batch size or use chunking")

        if "numeric" in str(error).lower():
            recovery_strategies.append("Clean input data and retry")

        return {
            "recoverable": len(recovery_strategies) > 0,
            "strategies": recovery_strategies,
            "error_type": type(error).__name__,
            "context": context,
        }

    def recover_from_database_failure(
        self, error: Exception, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Recover from database failures."""
        recovery_strategies = []

        if "connection" in str(error).lower():
            recovery_strategies.append("Retry with exponential backoff")

        if "constraint" in str(error).lower():
            recovery_strategies.append("Use UPSERT instead of INSERT")

        if "timeout" in str(error).lower():
            recovery_strategies.append("Reduce batch size")

        if "permission" in str(error).lower():
            recovery_strategies.append("Check database permissions")

        return {
            "recoverable": len(recovery_strategies) > 0,
            "strategies": recovery_strategies,
            "error_type": type(error).__name__,
            "context": context,
        }

    def recover_from_validation_failure(
        self, error: Exception, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Recover from validation failures."""
        recovery_strategies = []

        if "missing" in str(error).lower():
            recovery_strategies.append("Add missing columns or data")

        if "invalid" in str(error).lower():
            recovery_strategies.append("Clean and validate input data")

        if "type" in str(error).lower():
            recovery_strategies.append("Convert data types")

        return {
            "recoverable": len(recovery_strategies) > 0,
            "strategies": recovery_strategies,
            "error_type": type(error).__name__,
            "context": context,
        }


# Global error handler instance
error_handler = ErrorHandler()
error_recovery = ErrorRecovery()


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.append(str(Path(__file__).parent.parent.parent))

    parser = argparse.ArgumentParser(description="Test error handling")
    parser.add_argument(
        "--test-calculation",
        action="store_true",
        help="Test calculation error handling",
    )
    parser.add_argument(
        "--test-database", action="store_true", help="Test database error handling"
    )
    parser.add_argument(
        "--test-validation", action="store_true", help="Test validation error handling"
    )

    args = parser.parse_args()

    if args.test_calculation:
        # Test calculation error handling
        try:
            raise CalculationError("Test calculation error")
        except Exception as e:
            result = error_handler.handle_calculation_error(e, {"test": True})
            print(f"Calculation error handled: {result}")

    if args.test_database:
        # Test database error handling
        try:
            raise DatabaseError("Test database error")
        except Exception as e:
            result = error_handler.handle_database_error(e, {"test": True})
            print(f"Database error handled: {result}")

    if args.test_validation:
        # Test validation error handling
        try:
            raise ValidationError("Test validation error")
        except Exception as e:
            result = error_handler.handle_validation_error(e, {"test": True})
            print(f"Validation error handled: {result}")

    # Print error summary
    summary = error_handler.get_error_summary()
    print(f"Error summary: {summary}")
