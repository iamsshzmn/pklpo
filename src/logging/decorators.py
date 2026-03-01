"""Logging decorators for common patterns.

This module provides decorators for timing, operation logging, etc.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from logging import Logger
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

T = TypeVar("T")


def performance_timer(
    logger: Logger,
    operation_name: str,
    log_args: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Log execution time for wrapped functions.

    Args:
        logger: Target logger.
        operation_name: Human-readable operation name.
        log_args: If True, log function arguments count.

    Returns:
        Callable: Decorator preserving the wrapped function.

    Example:
        @performance_timer(logger, "calculate_indicators")
        def calculate(df, symbols):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception:
                duration = time.perf_counter() - start
                logger.error(
                    "Operation %s failed duration=%.3fs",
                    operation_name,
                    duration,
                    exc_info=True,
                )
                raise
            duration = time.perf_counter() - start
            if log_args:
                logger.debug(
                    "Operation %s completed duration=%.3fs args=%d kwargs=%d",
                    operation_name,
                    duration,
                    len(args),
                    len(kwargs),
                )
            else:
                logger.debug(
                    "Operation %s completed duration=%.3fs",
                    operation_name,
                    duration,
                )
            return result

        return wrapper

    return decorator


@dataclass
class OperationContext:
    """Context for tracking an operation's progress and metrics."""

    operation: str
    module: str
    logger: Logger
    start_time: float = field(default_factory=time.perf_counter)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get elapsed time in seconds."""
        return time.perf_counter() - self.start_time

    def set_metric(self, key: str, value: Any) -> None:
        """Set a metric value."""
        self.metrics[key] = value

    def log_progress(self, message: str, **kwargs: Any) -> None:
        """Log a progress message."""
        self.logger.info(f"{self.operation}: {message}", **kwargs)


@contextmanager
def log_operation(
    logger: Logger,
    operation: str,
    module: str = "",
    log_start: bool = True,
    log_end: bool = True,
) -> Generator[OperationContext, None, None]:
    """Context manager for logging operation start/end with timing.

    Args:
        logger: Target logger.
        operation: Operation name.
        module: Module name (optional).
        log_start: Log when operation starts.
        log_end: Log when operation completes.

    Yields:
        OperationContext for tracking metrics.

    Example:
        with log_operation(logger, "sync_data", "candles") as ctx:
            ctx.set_metric("symbols", 100)
            # ... do work ...
        # Logs: sync_data completed in 1.23s
    """
    ctx = OperationContext(
        operation=operation,
        module=module,
        logger=logger,
    )

    if log_start:
        if module:
            logger.info(f"[{module}] Starting {operation}")
        else:
            logger.info(f"Starting {operation}")

    try:
        yield ctx
    except Exception as e:
        duration = ctx.duration
        logger.error(
            f"{operation} failed after {duration:.3f}s: {e}",
            exc_info=True,
        )
        raise
    else:
        if log_end:
            duration = ctx.duration
            metrics_str = ""
            if ctx.metrics:
                metrics_str = " | " + ", ".join(
                    f"{k}={v}" for k, v in ctx.metrics.items()
                )
            if module:
                logger.info(
                    f"[{module}] {operation} completed in {duration:.3f}s{metrics_str}"
                )
            else:
                logger.info(f"{operation} completed in {duration:.3f}s{metrics_str}")


def log_function_call(
    logger: Logger | None = None,
    level: str = "DEBUG",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to log function calls.

    Args:
        logger: Target logger. If None, uses module logger.
        level: Log level for messages.

    Returns:
        Decorator function.

    Example:
        @log_function_call()
        def process_data(data):
            ...
    """
    import logging

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)
        log_level = getattr(logging, level.upper(), logging.DEBUG)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            logger.log(
                log_level,
                f"Calling {func.__name__} with {len(args)} args, {len(kwargs)} kwargs",
            )
            try:
                result = func(*args, **kwargs)
                logger.log(log_level, f"{func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        return wrapper

    return decorator
