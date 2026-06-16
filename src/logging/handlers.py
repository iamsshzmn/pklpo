"""Log handlers - console and file handlers.

This module provides handler factories for console and file output.

Environment variables:
    LOG_FORMAT: text|json (default: text)
"""

from __future__ import annotations

import logging
from logging import Handler
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING

from .config import (
    get_log_backup_count,
    get_log_dir,
    get_log_file_max_bytes,
    get_log_format,
    get_verbosity,
)
from .context import ContextFilter
from .formatters import _build_formatter
from .levels import Verbosity

if TYPE_CHECKING:
    from pathlib import Path

# Log directory - lazily initialized
_log_dir: Path | None = None


def get_log_directory() -> Path:
    """Get the log directory, creating it if needed.

    Returns:
        Path to log directory.
    """
    global _log_dir
    if _log_dir is None:
        _log_dir = get_log_dir()
    return _log_dir


# Backward compatibility alias
LOG_DIR = property(lambda self: get_log_directory())


def _build_console_handler(
    use_json: bool | None = None,
    verbosity: Verbosity | None = None,
) -> Handler:
    """Create a stream handler for stdout.

    Args:
        use_json: Override format (None = use env var).
        verbosity: Override verbosity (None = use global setting).

    Returns:
        Handler: Configured stream handler.
    """
    handler = logging.StreamHandler()

    # Set level based on verbosity
    verbosity = verbosity or get_verbosity()
    level_map = {
        Verbosity.QUIET: logging.WARNING,
        Verbosity.NORMAL: logging.INFO,
        Verbosity.VERBOSE: logging.DEBUG,
        Verbosity.DEBUG: logging.DEBUG,
    }
    handler.setLevel(level_map.get(verbosity, logging.INFO))

    # Set formatter based on format preference
    if use_json is None:
        use_json = get_log_format() == "json"
    handler.setFormatter(_build_formatter(use_json=use_json))

    # Add context filter to inject run_id, symbol, timeframe
    handler.addFilter(ContextFilter())

    return handler


def _build_file_handler(
    filename: str,
    level: int = logging.DEBUG,
    max_bytes: int | None = None,
    backup_count: int | None = None,
    log_dir: Path | None = None,
) -> Handler:
    """Create a rotating file handler.

    Args:
        filename: Target log file name.
        level: Minimum log level.
        max_bytes: Max file size before rotation (None = use env var).
        backup_count: Number of backup files (None = use env var).
        log_dir: Log directory (None = use default).

    Returns:
        Handler: Configured rotating handler.
    """
    if log_dir is None:
        log_dir = get_log_directory()

    if max_bytes is None:
        max_bytes = get_log_file_max_bytes()

    if backup_count is None:
        backup_count = get_log_backup_count()

    handler = RotatingFileHandler(
        log_dir / filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    # File handlers always use JSON for structured log aggregation (Promtail/Loki)
    handler.setFormatter(_build_formatter(use_json=True))

    # Add context filter to inject run_id, symbol, timeframe, component, error_type
    handler.addFilter(ContextFilter())

    return handler
