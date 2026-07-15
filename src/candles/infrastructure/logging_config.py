# fmt: off
"""Deprecated market metadata logging compatibility helpers."""

from __future__ import annotations

import os
import warnings
from typing import Any

from src.logging import get_logger as _get_logger, setup_logging

warnings.warn(
    "src.market_meta.infrastructure.logging_config is deprecated. "
    "Use src.logging instead.",
    DeprecationWarning,
    stacklevel=2,
)

LOGGER_NAME = "market_meta"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DEFAULT_LOG_FILE = "/opt/airflow/project/logs/market_meta.log"
MAX_LOG_SIZE = 10 * 1024 * 1024
BACKUP_COUNT = 5


class MarketMetaLogger:
    """Compatibility facade over :mod:`src.logging`."""

    def __init__(self, name: str = LOGGER_NAME) -> None:
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
        del log_file, log_format, console_output, file_output, max_size, backup_count
        if self._configured:
            return
        setup_logging(level=level)
        self._configured = True

    def get_logger(self, name: str | None = None) -> Any:
        if name:
            return _get_logger(f"{self.name}.{name}")
        return self.logger

    def log_validation_result(
        self,
        symbol: str,
        violations: list[str],
        warnings_list: list[str] | None = None,
    ) -> None:
        if violations:
            self.logger.warning(
                "Validation failed for %s: %s violations", symbol, len(violations)
            )
            for index, violation in enumerate(violations, 1):
                self.logger.warning("  %s. %s", index, violation)
        else:
            self.logger.info("Validation passed for %s", symbol)

        for warning in warnings_list or []:
            self.logger.info("Warning for %s: %s", symbol, warning)

    def log_cache_status(self, status: dict[str, Any]) -> None:
        self.logger.info(
            "Cache status: valid=%s, instruments=%s, ttl=%.1fh",
            status.get("is_valid"),
            status.get("instruments_count"),
            status.get("ttl_hours", 0),
        )

    def log_refresh_status(
        self,
        success: bool,
        instruments_count: int = 0,
        error: str | None = None,
    ) -> None:
        if success:
            self.logger.info(
                "Metadata refresh completed: %s instruments", instruments_count
            )
        else:
            self.logger.error("Metadata refresh failed: %s", error)

    def log_risk_check(self, symbol: str, risk_level: str, details: str) -> None:
        if risk_level.upper() in {"HIGH", "CRITICAL"}:
            self.logger.warning("High risk for %s: %s", symbol, details)
        else:
            self.logger.info("Risk check for %s: %s", symbol, details)


_market_meta_logger = MarketMetaLogger()


def get_logger(name: str | None = None) -> Any:
    if name:
        return _get_logger(f"{LOGGER_NAME}.{name}")
    return _market_meta_logger.get_logger()


def configure_logging(**kwargs: Any) -> None:
    _market_meta_logger.configure(**kwargs)


def log_validation_result(
    symbol: str,
    violations: list[str],
    warnings_list: list[str] | None = None,
) -> None:
    _market_meta_logger.log_validation_result(symbol, violations, warnings_list)


def log_cache_status(status: dict[str, Any]) -> None:
    _market_meta_logger.log_cache_status(status)


def log_refresh_status(
    success: bool,
    instruments_count: int = 0,
    error: str | None = None,
) -> None:
    _market_meta_logger.log_refresh_status(success, instruments_count, error)


def log_risk_check(symbol: str, risk_level: str, details: str) -> None:
    _market_meta_logger.log_risk_check(symbol, risk_level, details)


def auto_configure() -> None:
    level = os.getenv("MARKET_META_LOG_LEVEL", DEFAULT_LOG_LEVEL)
    configure_logging(level=level)


__all__ = [
    "BACKUP_COUNT",
    "DEFAULT_LOG_FILE",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_LOG_LEVEL",
    "LOGGER_NAME",
    "MAX_LOG_SIZE",
    "MarketMetaLogger",
    "auto_configure",
    "configure_logging",
    "get_logger",
    "log_cache_status",
    "log_refresh_status",
    "log_risk_check",
    "log_validation_result",
]
# fmt: on
