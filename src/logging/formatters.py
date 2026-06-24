"""Log formatters - text and JSON formats.

This module provides formatters for log output.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from logging import Formatter, LogRecord


class JsonFormatter(Formatter):
    """JSON formatter for structured logging.

    Produces JSON lines format suitable for log aggregation tools.
    Timestamps are ISO 8601 with millisecond precision and explicit UTC offset
    (``2006-01-02T15:04:05.000Z`` — matches the Promtail timestamp stage format).
    """

    def formatTime(self, record: LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        """Return ISO 8601 timestamp with milliseconds and UTC Z suffix.

        Overrides the base ``Formatter.formatTime`` to produce sub-second
        ordering and a Promtail-compatible format without relying on
        locale-dependent ``%Z`` or the Python 3.11-only ``datetime.UTC``.

        Example output: ``2026-06-13T18:30:45.123Z``
        """
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

    def format(self, record: LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "component": getattr(record, "component", "-"),
            "message": record.getMessage(),
            "run_id": getattr(record, "run_id", "-"),
            "symbol": getattr(record, "symbol", "-"),
            "timeframe": getattr(record, "timeframe", "-"),
            "trace_id": getattr(record, "trace_id", "-"),
            "span_id": getattr(record, "span_id", "-"),
            "error_type": getattr(record, "error_type", "-"),
            "category": getattr(record, "category", "-"),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        for field_name in ("event", "task_id", "duration_ms"):
            field_value = getattr(record, field_name, None)
            if field_value is not None:
                log_data[field_name] = field_value

        return json.dumps(log_data)


class CompactFormatter(Formatter):
    """Compact formatter for high-volume logs.

    Uses minimal format: timestamp level message
    """

    def __init__(self) -> None:
        super().__init__(
            "%(asctime)s [%(levelname).1s] %(message)s",
            "%H:%M:%S",
        )


def _build_formatter(use_json: bool = False, compact: bool = False) -> Formatter:
    """Return a formatter with unified message format including context.

    Args:
        use_json: If True, use JSON formatter for structured logging.
        compact: If True, use compact formatter (ignored if use_json=True).

    Returns:
        Formatter: Shared formatter for all handlers.

    Format includes:
        - timestamp
        - level
        - run_id (correlation ID)
        - symbol (if set)
        - timeframe (if set)
        - logger name
        - message
    """
    if use_json:
        return JsonFormatter()

    if compact:
        return CompactFormatter()

    return Formatter(
        "%(asctime)s [%(levelname)s] [%(run_id)s] %(symbol)s/%(timeframe)s %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
