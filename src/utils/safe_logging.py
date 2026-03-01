"""
Утилиты для безопасного логирования

DEPRECATED: This module now delegates to src.logging.
Use `from src.logging import SensitiveDataFilter, get_logger` directly.
"""

import warnings

from src.logging import (
    SensitiveDataFilter,
    get_logger,
    setup_logging,
)

# Emit deprecation warning
warnings.warn(
    "src.utils.safe_logging is deprecated. Use src.logging instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = get_logger(__name__)


def setup_safe_logging(
    level: str = "INFO",
    log_file: str | None = None,
    format_string: str | None = None,
):
    """
    Настраивает безопасное логирование.

    DEPRECATED: Use src.logging.setup_logging instead.
    SensitiveDataFilter is automatically applied.
    """
    return setup_logging(level=level)


def log_function_call(
    func_name: str, args: tuple | None = None, kwargs: dict | None = None
):
    """
    Декоратор для логирования вызовов функций.

    DEPRECATED: Use src.logging.log_function_call instead.
    """
    from src.logging import log_function_call as _log_function_call

    return _log_function_call()


def log_database_operation(operation: str, table: str, **kwargs):
    """
    Логирует операции с базой данных.
    """
    context = f"Таблица: {table}"
    if kwargs:
        context += f", Параметры: {kwargs}"
    logger.info(f"Операция БД: {operation} - {context}")


def log_api_request(method: str, url: str, status_code: int | None = None, **kwargs):
    """
    Логирует API запросы.
    """
    context = f"URL: {url}"
    if status_code:
        context += f", Статус: {status_code}"
    if kwargs:
        context += f", Параметры: {kwargs}"
    logger.info(f"API запрос: {method} - {context}")


__all__ = [
    "SensitiveDataFilter",
    "log_api_request",
    "log_database_operation",
    "log_function_call",
    "setup_safe_logging",
]
