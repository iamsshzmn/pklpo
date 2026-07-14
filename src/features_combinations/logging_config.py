"""Конфигурация логирования для features_combinations.

DEPRECATED: This module now delegates to src.logging.
Use `from src.logging import get_logger` directly.
"""

import warnings

from src.logging import get_logger as _get_logger, setup_logging

# Emit deprecation warning
warnings.warn(
    "src.features_combinations.logging_config is deprecated. Use src.logging instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Base logger name
BASE_LOGGER_NAME = "features_combinations"


def get_combinations_logger(name: str | None = None):
    """
    Получить логгер для features_combinations.

    Args:
        name: Имя дочернего логгера (например, "service", "calculator")

    Returns:
        Настроенный логгер
    """
    if not name:
        return _get_logger(BASE_LOGGER_NAME)
    return _get_logger(f"{BASE_LOGGER_NAME}.{name}")


def setup_combinations_logging(level: str = "INFO", verbose: bool = False):
    """
    Настроить уровень логирования для features_combinations.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        verbose: Принудительно установить DEBUG уровень

    Returns:
        Базовый логгер
    """
    return setup_logging(level=level, verbose=verbose)


__all__ = [
    "BASE_LOGGER_NAME",
    "get_combinations_logger",
    "setup_combinations_logging",
]
