"""Log formatters - text and JSON formats.

This module provides formatters for log output.
"""

from __future__ import annotations

import json
from logging import Formatter, LogRecord


class JsonFormatter(Formatter):
    """JSON formatter for structured logging.

    Produces JSON lines format suitable for log aggregation tools.
    """

    def format(self, record: LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": getattr(record, "run_id", "-"),
            "symbol": getattr(record, "symbol", "-"),
            "timeframe": getattr(record, "timeframe", "-"),
            "category": getattr(record, "category", "-"),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

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
