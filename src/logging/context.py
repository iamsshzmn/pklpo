"""Async-safe log context and context filter.

This module provides correlation ID support and context injection
for log records.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from logging import LogRecord
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass(frozen=True)
class _LogContextState:
    """Immutable log context state stored per async context."""

    run_id: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    component: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


_EMPTY_CONTEXT = _LogContextState()
_log_context: ContextVar[_LogContextState] = ContextVar(
    "pklpo_log_context",
    default=_EMPTY_CONTEXT,
)


def generate_run_id() -> str:
    """Generate a unique run ID for correlation."""
    return uuid.uuid4().hex[:12]


@contextmanager
def set_log_context(
    run_id: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    component: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    **extra: Any,
) -> Generator[str, None, None]:
    """
    Context manager to set log context for the current async context.

    Args:
        run_id: Correlation ID (auto-generated if None)
        symbol: Trading symbol
        timeframe: Timeframe
        component: Logical component name (e.g. "swap_sync", "repair", "features")
        trace_id: Optional trace ID override
        span_id: Optional span ID override
        **extra: Additional context fields

    Yields:
        The run_id being used

    Example:
        with set_log_context(symbol="BTC-USDT", timeframe="1m", component="swap_sync") as run_id:
            logger.info("Processing")  # Logs include run_id, symbol, timeframe, component
    """
    current = _LogContextState(
        run_id=run_id or generate_run_id(),
        symbol=symbol,
        timeframe=timeframe,
        component=component,
        trace_id=trace_id,
        span_id=span_id,
        extra=dict(extra),
    )
    token = _log_context.set(current)

    try:
        yield current.run_id or ""
    finally:
        _log_context.reset(token)


def get_current_run_id() -> str | None:
    """Get the current run ID from async-local context."""
    return _log_context.get().run_id


def get_current_context() -> dict[str, Any]:
    """Get the current log context as a dictionary.

    Returns:
        Dictionary with run_id, symbol, timeframe, component, and any extra fields.
    """
    context = _log_context.get()
    return {
        "run_id": context.run_id,
        "symbol": context.symbol,
        "timeframe": context.timeframe,
        "component": context.component,
        "trace_id": context.trace_id,
        "span_id": context.span_id,
        **context.extra,
    }


class ContextFilter(logging.Filter):
    """
    Filter that adds context fields to log records.

    Adds run_id, symbol, and timeframe from async-local storage.
    """

    def filter(self, record: LogRecord) -> bool:
        """Add context fields to the log record."""
        context = _log_context.get()
        record.run_id = context.run_id or "-"
        record.symbol = context.symbol or "-"
        record.timeframe = context.timeframe or "-"
        record.component = getattr(record, "component", None) or context.component or "-"
        trace_id, span_id = _get_active_trace_ids()
        record.trace_id = (
            getattr(record, "trace_id", None) or context.trace_id or trace_id
        )
        record.span_id = getattr(record, "span_id", None) or context.span_id or span_id
        # error_type: caller can set via extra={"error_type": ...}; default "-"
        if not hasattr(record, "error_type"):
            record.error_type = "-"
        # Add category if present
        record.category = getattr(record, "category", "-")
        # Add any extra context fields
        for key, value in context.extra.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


def _get_active_trace_ids() -> tuple[str, str]:
    try:
        from src.logging.tracing import get_trace_ids
    except ImportError:
        return "-", "-"

    return get_trace_ids()
