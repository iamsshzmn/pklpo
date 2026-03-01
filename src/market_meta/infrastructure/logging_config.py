"""
Централизованная конфигурация логирования для модуля market_meta.

DEPRECATED: This module now delegates to src.logging.
Use `from src.logging import get_logger` directly.
"""

import os
import warnings
from typing import Any

from src.logging import get_logger as _get_logger, setup_logging

# Emit deprecation warning
warnings.warn(
    "src.market_meta.infrastructure.logging_config is deprecated. "
    "Use src.logging instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Constants for backward compatibility
LOGGER_NAME = "market_meta"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DEFAULT_LOG_FILE = "/opt/airflow/project/logs/market_meta.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


class MarketMetaLogger:
    """
    Централизованный логгер для модуля market_meta.

    DEPRECATED: Use src.logging directly.
    """

    def __init__(self, name: str = LOGGER_NAME):
        self.name = name
        self.logger = _get_logger(name)
        self._configured = False

    def configure(
        self,
        level: str = DEFAULT_LOG_LEVEL,
        log_file: str | None = None,
        log_format: str = DEFAULT_LOG_FORMAT,
        console_output: bool = True,
        file_output: bool = True,
        max_size: int = MAX_LOG_SIZE,
        backup_count: int = BACKUP_COUNT,
    ) -> None:
        """Настраивает логирование для модуля."""
        if self._configured:
            return
        setup_logging(level=level)
        self._configured = True

    def get_logger(self, name: str | None = None):
        """Возвращает логгер для указанного компонента."""
        if name:
            return _get_logger(f"{self.name}.{name}")
        return self.logger

    def log_validation_result(
        self, symbol: str, violations: list[str], warnings_list: list[str] | None = None
    ) -> None:
        """Логирует результат валидации ордера."""
        if violations:
            self.logger.warning(
                f"Валидация ордера {symbol} не прошла: {len(violations)} нарушений"
            )
            for i, violation in enumerate(violations, 1):
                self.logger.warning(f"  {i}. {violation}")
        else:
            self.logger.info(f"Валидация ордера {symbol} прошла успешно")

        if warnings_list:
            for warning in warnings_list:
                self.logger.info(f"Предупреждение для {symbol}: {warning}")

    def log_cache_status(self, status: dict[str, Any]) -> None:
        """Логирует статус кэша."""
        self.logger.info(
            f"Статус кэша: актуален={status.get('is_valid')}, "
            f"инструментов={status.get('instruments_count')}, "
            f"TTL={status.get('ttl_hours', 0):.1f}ч"
        )

    def log_refresh_status(
        self, success: bool, instruments_count: int = 0, error: str | None = None
    ) -> None:
        """Логирует статус обновления метаданных."""
        if success:
            self.logger.info(
                f"Обновление метаданных успешно завершено: {instruments_count} инструментов"
            )
        else:
            self.logger.error(f"Ошибка обновления метаданных: {error}")

    def log_risk_check(self, symbol: str, risk_level: str, details: str) -> None:
        """Логирует проверку рисков."""
        if risk_level.upper() in ["HIGH", "CRITICAL"]:
            self.logger.warning(f"Высокий риск для {symbol}: {details}")
        else:
            self.logger.info(f"Проверка рисков {symbol}: {details}")


# Global instance
_market_meta_logger = MarketMetaLogger()


def get_logger(name: str | None = None):
    """Возвращает настроенный логгер для модуля market_meta."""
    if name:
        return _get_logger(f"{LOGGER_NAME}.{name}")
    return _market_meta_logger.get_logger()


def configure_logging(**kwargs) -> None:
    """Настраивает логирование для модуля market_meta."""
    _market_meta_logger.configure(**kwargs)


def log_validation_result(
    symbol: str, violations: list[str], warnings_list: list[str] | None = None
) -> None:
    """Логирует результат валидации ордера."""
    _market_meta_logger.log_validation_result(symbol, violations, warnings_list)


def log_cache_status(status: dict[str, Any]) -> None:
    """Логирует статус кэша."""
    _market_meta_logger.log_cache_status(status)


def log_refresh_status(
    success: bool, instruments_count: int = 0, error: str | None = None
) -> None:
    """Логирует статус обновления метаданных."""
    _market_meta_logger.log_refresh_status(success, instruments_count, error)


def log_risk_check(symbol: str, risk_level: str, details: str) -> None:
    """Логирует проверку рисков."""
    _market_meta_logger.log_risk_check(symbol, risk_level, details)


def auto_configure() -> None:
    """Автоматическая настройка логирования из переменных окружения."""
    level = os.getenv("MARKET_META_LOG_LEVEL", DEFAULT_LOG_LEVEL)
    configure_logging(level=level)


# Auto-configure on import
auto_configure()


__all__ = [
    "LOGGER_NAME",
    "MarketMetaLogger",
    "auto_configure",
    "configure_logging",
    "get_logger",
    "log_cache_status",
    "log_refresh_status",
    "log_risk_check",
    "log_validation_result",
]
