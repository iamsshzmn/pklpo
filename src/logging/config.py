"""Logging configuration - verbosity and category management.

This module handles global logging state and environment-based configuration.

Environment variables:
    LOG_VERBOSITY: quiet|normal|verbose|debug (default: normal)
    LOG_CATEGORIES: comma-separated list to enable (default: all)
    LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
    LOG_FORMAT: text|json (default: text)
    LOG_DIR: Directory for log files (default: project_root/logs)
    LOG_FILE_MAX_MB: Max size per log file in MB (default: 10)
    LOG_BACKUP_COUNT: Number of backup files to keep (default: 5)

Legacy env vars (still supported for backward compatibility):
    FEATURES_LOG_VERBOSITY -> LOG_VERBOSITY
    FEATURES_LOG_CATEGORIES -> LOG_CATEGORIES
    FEATURES_LOG_FORMAT -> LOG_FORMAT
"""

from __future__ import annotations

import os
from pathlib import Path

from .levels import LogCategory, Verbosity

# Global verbosity setting
_verbosity: Verbosity = Verbosity.NORMAL
_enabled_categories: set[LogCategory] = set(LogCategory)


def get_verbosity() -> Verbosity:
    """Get current verbosity level."""
    return _verbosity


def set_verbosity(level: Verbosity | str | int) -> None:
    """Set global verbosity level.

    Args:
        level: Verbosity enum, string name, or integer value.
    """
    global _verbosity
    if isinstance(level, Verbosity):
        _verbosity = level
    elif isinstance(level, str):
        _verbosity = Verbosity[level.upper()]
    elif isinstance(level, int):
        _verbosity = Verbosity(level)
    else:
        raise ValueError(f"Invalid verbosity: {level}")


def is_category_enabled(category: LogCategory) -> bool:
    """Check if a log category is enabled."""
    return category in _enabled_categories


def set_enabled_categories(categories: set[LogCategory] | None) -> None:
    """Set which categories are enabled. None enables all."""
    global _enabled_categories
    _enabled_categories = categories if categories is not None else set(LogCategory)


def should_log(category: LogCategory, min_verbosity: Verbosity) -> bool:
    """Check if a message should be logged based on category and verbosity.

    Args:
        category: Log category.
        min_verbosity: Minimum verbosity level required to log.

    Returns:
        True if the message should be logged.
    """
    if not is_category_enabled(category):
        return False
    return _verbosity.value >= min_verbosity.value


def get_log_dir() -> Path:
    """Get the log directory from environment or default.

    Returns:
        Path to log directory.
    """
    env_dir = os.environ.get("LOG_DIR")
    log_dir = Path(env_dir) if env_dir else Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_format() -> str:
    """Get log format from environment.

    Returns:
        'text' or 'json'
    """
    # Check new env var first, then legacy
    fmt = os.environ.get("LOG_FORMAT") or os.environ.get("FEATURES_LOG_FORMAT", "text")
    return fmt.lower()


def get_log_level() -> str:
    """Get log level from environment.

    Returns:
        Log level string (DEBUG, INFO, WARNING, ERROR)
    """
    return os.environ.get("LOG_LEVEL", "INFO").upper()


def get_log_file_max_bytes() -> int:
    """Get max log file size in bytes.

    Returns:
        Max file size in bytes.
    """
    mb = int(os.environ.get("LOG_FILE_MAX_MB", "10"))
    return mb * 1024 * 1024


def get_log_backup_count() -> int:
    """Get number of backup log files to keep.

    Returns:
        Number of backup files.
    """
    return int(os.environ.get("LOG_BACKUP_COUNT", "5"))


def _init_from_env() -> None:
    """Initialize logging settings from environment variables."""
    global _verbosity, _enabled_categories

    # LOG_VERBOSITY or FEATURES_LOG_VERBOSITY: quiet|normal|verbose|debug
    verbosity_str = (
        os.environ.get("LOG_VERBOSITY")
        or os.environ.get("FEATURES_LOG_VERBOSITY", "normal")
    ).lower()
    try:
        _verbosity = Verbosity[verbosity_str.upper()]
    except KeyError:
        _verbosity = Verbosity.NORMAL

    # LOG_CATEGORIES or FEATURES_LOG_CATEGORIES: comma-separated list
    categories_str = os.environ.get("LOG_CATEGORIES") or os.environ.get(
        "FEATURES_LOG_CATEGORIES", ""
    )
    if categories_str:
        enabled = set()
        for cat_name in categories_str.split(","):
            cat_name = cat_name.strip().upper()
            try:
                enabled.add(LogCategory[cat_name])
            except KeyError:
                pass  # Ignore invalid category names
        _enabled_categories = enabled if enabled else set(LogCategory)
    else:
        _enabled_categories = set(LogCategory)


# Initialize from environment on module load
_init_from_env()
