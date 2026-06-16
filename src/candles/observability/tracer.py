"""Correlation tracing for candle sync runs.

Provides a run-scoped run_id that propagates through structured log fields,
enabling end-to-end traceability of sync operations.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from src.logging import get_logger
from src.logging.context import (
    generate_run_id,
    get_current_context,
    get_current_run_id,
    set_log_context,
)

logger = logging.getLogger(__name__)

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_trace_context: ContextVar[dict[str, str] | None] = ContextVar(
    "trace_context",
    default=None,
)


def get_correlation_id() -> str:
    """Return the current run_id through the legacy correlation_id alias."""
    return _correlation_id.get()


def get_trace_context() -> dict[str, str]:
    return _trace_context.get() or {}


@contextmanager
def trace_sync_run(
    *,
    mode: str = "",
    symbols_count: int = 0,
    run_id: str | None = None,
    correlation_id: str | None = None,
):
    """Context manager that binds a run_id for the duration of a sync run.

    Usage::

        with trace_sync_run(mode="fast", symbols_count=200) as run_id:
            # all logging within this block can access run_id
            ...
    """
    if run_id is not None and correlation_id is not None and run_id != correlation_id:
        raise ValueError("run_id and correlation_id must match when both are provided")

    rid = run_id or correlation_id or get_current_run_id() or generate_run_id()
    token_id = _correlation_id.set(rid)
    token_ctx = _trace_context.set(
        {
            "run_id": rid,
            "mode": mode,
            "symbols_count": str(symbols_count),
        }
    )
    with set_log_context(run_id=rid, component="swap_sync"):
        logger.info(
            "sync_run.start run_id=%s mode=%s symbols=%d",
            rid,
            mode,
            symbols_count,
        )
        try:
            yield rid
        finally:
            logger.info("sync_run.end run_id=%s", rid)
            _correlation_id.reset(token_id)
            _trace_context.reset(token_ctx)


class CorrelationLogFilter(logging.Filter):
    """Logging filter that injects run_id into every log record.

    ``correlation_id`` is retained as a backward-compatible alias.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        run_id = _correlation_id.get()
        record.run_id = getattr(record, "run_id", None) or run_id
        record.correlation_id = run_id
        return True


def trace_event(event: str, **kwargs: Any) -> None:
    """Emit a structured trace event at INFO level."""
    context = get_current_context()
    run_id = _correlation_id.get() or context.get("run_id") or generate_run_id()
    component = str(kwargs.pop("component", None) or context.get("component") or "trace")
    symbol = kwargs.pop("symbol", None) or context.get("symbol")
    timeframe = kwargs.pop("timeframe", None) or context.get("timeframe")
    task_id = kwargs.pop("task_id", None) or context.get("task_id")
    error_type = kwargs.pop("error_type", "-")
    exc_info = kwargs.pop("exc_info", None)

    extra: dict[str, Any] = {
        "event": event,
        "error_type": error_type,
        **kwargs,
    }
    if task_id is not None:
        extra["task_id"] = task_id

    with set_log_context(
        run_id=str(run_id),
        component=component,
        symbol=str(symbol) if symbol is not None else None,
        timeframe=str(timeframe) if timeframe is not None else None,
        task_id=str(task_id) if task_id is not None else None,
    ):
        level = logging.ERROR if error_type != "-" or exc_info else logging.INFO
        get_logger(component).log(level, event, extra=extra, exc_info=exc_info)
