"""Correlation tracing for candle sync runs.

Provides a run-scoped correlation_id that propagates through all log messages
via contextvars, enabling end-to-end traceability of sync operations.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger(__name__)

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_trace_context: ContextVar[dict[str, str] | None] = ContextVar(
    "trace_context",
    default=None,
)


def get_correlation_id() -> str:
    return _correlation_id.get()


def get_trace_context() -> dict[str, str]:
    return _trace_context.get() or {}


@contextmanager
def trace_sync_run(
    *,
    mode: str = "",
    symbols_count: int = 0,
    correlation_id: str | None = None,
):
    """Context manager that binds a correlation_id for the duration of a sync run.

    Usage::

        with trace_sync_run(mode="fast", symbols_count=200) as cid:
            # all logging within this block can access cid
            ...
    """
    cid = correlation_id or uuid.uuid4().hex[:12]
    token_id = _correlation_id.set(cid)
    token_ctx = _trace_context.set(
        {
            "correlation_id": cid,
            "mode": mode,
            "symbols_count": str(symbols_count),
        }
    )
    logger.info(
        "sync_run.start correlation_id=%s mode=%s symbols=%d",
        cid,
        mode,
        symbols_count,
    )
    try:
        yield cid
    finally:
        logger.info("sync_run.end correlation_id=%s", cid)
        _correlation_id.reset(token_id)
        _trace_context.reset(token_ctx)


class CorrelationLogFilter(logging.Filter):
    """Logging filter that injects correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get()
        return True


def trace_event(event: str, **kwargs: Any) -> None:
    """Emit a structured trace event at INFO level."""
    cid = _correlation_id.get()
    parts = [f"{k}={v}" for k, v in kwargs.items()]
    extra = f" {' '.join(parts)}" if parts else ""
    logger.info("%s correlation_id=%s%s", event, cid, extra)
