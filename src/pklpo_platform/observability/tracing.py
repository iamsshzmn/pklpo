"""Tracing re-exports for the platform observability facade."""

from __future__ import annotations

from src.logging.tracing import (
    configure_tracing,
    get_trace_ids,
    set_span_attributes,
    start_span,
)

__all__ = [
    "configure_tracing",
    "get_trace_ids",
    "set_span_attributes",
    "start_span",
]
