"""Structured logging pipeline for candle sync.

Uses stdlib logging with a JSON formatter and CorrelationLogFilter.
No external dependencies required (no structlog needed).

Usage::

    from src.candles.observability.structlog_config import setup_candles_logging

    setup_candles_logging()  # call once at startup
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from .tracer import CorrelationLogFilter, get_correlation_id

CANDLES_LOGGER_NAME = "src.candles"


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    Fields: timestamp, level, logger, correlation_id, message, and any extras.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", ""),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_candles_logging(
    *,
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure the ``src.candles`` logger hierarchy.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, use JSONFormatter; otherwise plain text.
    """
    candles_logger = logging.getLogger(CANDLES_LOGGER_NAME)
    candles_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls
    if any(isinstance(h, logging.StreamHandler) for h in candles_logger.handlers):
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(candles_logger.level)

    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | "
                "cid=%(correlation_id)s | %(message)s"
            )
        )

    handler.addFilter(CorrelationLogFilter())
    candles_logger.addHandler(handler)
    candles_logger.propagate = False
