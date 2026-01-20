"""Конфигурация логирования для features_combinations."""

import logging
import os

# Базовое имя логгера
BASE_LOGGER_NAME = "features_combinations"

# Глобальная переменная для базового логгера
_base_logger: logging.Logger | None = None


def _ensure_base_logger() -> logging.Logger:
    """Создать и настроить базовый логгер, если ещё не создан."""
    global _base_logger

    if _base_logger is not None:
        return _base_logger

    # Создаём базовый логгер
    _base_logger = logging.getLogger(BASE_LOGGER_NAME)

    # Если уже настроен, возвращаем
    if _base_logger.handlers:
        return _base_logger

    # Уровень логирования из переменной окружения
    log_level = os.getenv("FEATURES_COMBINATIONS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    _base_logger.setLevel(level)

    # Создаём консольный handler, если его нет
    if not any(isinstance(h, logging.StreamHandler) for h in _base_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Формат: timestamp level logger_name message
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        _base_logger.addHandler(console_handler)

    # Не пропускаем сообщения в родительские логгеры
    _base_logger.propagate = False

    return _base_logger


def get_combinations_logger(name: str | None = None) -> logging.Logger:
    """
    Получить логгер для features_combinations.

    Args:
        name: Имя дочернего логгера (например, "service", "calculator")

    Returns:
        Настроенный логгер

    Examples:
        >>> logger = get_combinations_logger()
        >>> logger.info("Base logger")
        >>> service_logger = get_combinations_logger("service")
        >>> service_logger.info("Service logger")
    """
    base = _ensure_base_logger()
    if not name:
        return base
    return base.getChild(name)


def setup_combinations_logging(
    level: str = "INFO", verbose: bool = False
) -> logging.Logger:
    """
    Настроить уровень логирования для features_combinations.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        verbose: Принудительно установить DEBUG уровень

    Returns:
        Базовый логгер
    """
    logger = _ensure_base_logger()

    if verbose:
        os.environ["FEATURES_COMBINATIONS_VERBOSE"] = "true"

    desired_level = (
        logging.DEBUG if verbose else getattr(logging, level.upper(), logging.INFO)
    )

    # Обновляем уровень для логгера и всех handlers
    logger.setLevel(desired_level)
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(desired_level)

    return logger
