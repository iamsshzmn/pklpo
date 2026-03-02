"""Thread-local log context and context filter.

This module provides correlation ID support and context injection
for log records.
"""

from __future__ import annotations

import logging
import threading
import uuid
from contextlib import contextmanager
from logging import LogRecord
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator


class _LogContext(threading.local):
    """Thread-local storage for log context data."""

    def __init__(self) -> None:
        super().__init__()
        self.run_id: str | None = None
        self.symbol: str | None = None
        self.timeframe: str | None = None
        self.extra: dict[str, Any] = {}


_log_context = _LogContext()


def generate_run_id() -> str:
    """Generate a unique run ID for correlation."""
    return uuid.uuid4().hex[:12]


@contextmanager
def set_log_context(
    run_id: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    **extra: Any,
) -> Generator[str, None, None]:
    """
    Context manager to set log context for the current thread.

    Args:
        run_id: Correlation ID (auto-generated if None)
        symbol: Trading symbol
        timeframe: Timeframe
        **extra: Additional context fields

    Yields:
        The run_id being used

    Example:
        with set_log_context(symbol="BTC-USDT", timeframe="1m") as run_id:
            logger.info("Processing")  # Logs include run_id, symbol, timeframe
    """
    # Save previous context
    prev_run_id = _log_context.run_id
    prev_symbol = _log_context.symbol
    prev_timeframe = _log_context.timeframe
    prev_extra = _log_context.extra.copy()

    # Set new context
    _log_context.run_id = run_id or generate_run_id()
    _log_context.symbol = symbol
    _log_context.timeframe = timeframe
    _log_context.extra = extra

    try:
        yield _log_context.run_id
    finally:
        # Restore previous context
        _log_context.run_id = prev_run_id
        _log_context.symbol = prev_symbol
        _log_context.timeframe = prev_timeframe
        _log_context.extra = prev_extra


def get_current_run_id() -> str | None:
    """Get the current run ID from thread-local context."""
    return _log_context.run_id


def get_current_context() -> dict[str, Any]:
    """Get the current log context as a dictionary.

    Returns:
        Dictionary with run_id, symbol, timeframe, and any extra fields.
    """
    return {
        "run_id": _log_context.run_id,
        "symbol": _log_context.symbol,
        "timeframe": _log_context.timeframe,
        **_log_context.extra,
    }


class ContextFilter(logging.Filter):
    """
    Filter that adds context fields to log records.

    Adds run_id, symbol, and timeframe from thread-local storage.
    """

    def filter(self, record: LogRecord) -> bool:
        """Add context fields to the log record."""
        record.run_id = _log_context.run_id or "-"
        record.symbol = _log_context.symbol or "-"
        record.timeframe = _log_context.timeframe or "-"
        # Add category if present
        record.category = getattr(record, "category", "-")
        # Add any extra context fields
        for key, value in _log_context.extra.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True
