"""
Централизованная система логирования для MTF модулей

DEPRECATED: This module now delegates to src.logging.
Use `from src.logging import get_logger, LogCategory` directly.
"""

import warnings
from datetime import datetime
from typing import Any

from src.logging import (
    get_logger,
    setup_logging,
)

# Emit deprecation warning
warnings.warn(
    "src.mtf.logging_config is deprecated. Use src.logging instead.",
    DeprecationWarning,
    stacklevel=2,
)


class MTFLogger:
    """Централизованный логгер для MTF системы.

    DEPRECATED: Use src.logging directly.
    """

    _initialized = False

    @classmethod
    def initialize(cls, log_dir: str = "logs/mtf", log_level: str = "INFO") -> None:
        """Инициализация системы логирования."""
        if cls._initialized:
            return
        setup_logging(level=log_level)
        cls._initialized = True

    @classmethod
    def get_logger(cls, module_name: str):
        """Получение логгера для модуля."""
        if not cls._initialized:
            cls.initialize()
        return get_logger(f"mtf.{module_name}")

    @classmethod
    def log_performance(
        cls,
        module_name: str,
        operation: str,
        duration: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Логирование производительности."""
        logger = cls.get_logger(module_name)
        logger.info(
            "PERFORMANCE | %s | %.3fs | %s",
            operation,
            duration,
            metadata or {},
        )

    @classmethod
    def log_error(
        cls,
        module_name: str,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Логирование ошибок с контекстом."""
        logger = cls.get_logger(module_name)
        logger.error(
            "ERROR | %s | %s | %s",
            type(error).__name__,
            str(error),
            context or {},
        )

    @classmethod
    def log_metrics(cls, module_name: str, metrics: dict[str, Any]) -> None:
        """Логирование метрик."""
        logger = cls.get_logger(module_name)
        logger.info("METRICS | %s", metrics)


# Backward compatibility functions
def get_context_logger():
    """Логгер для Context модуля."""
    return get_logger("mtf.context")


def get_triggers_logger():
    """Логгер для Triggers модуля."""
    return get_logger("mtf.triggers")


def get_consensus_logger():
    """Логгер для Consensus модуля."""
    return get_logger("mtf.consensus")


def get_pipeline_logger():
    """Логгер для Pipeline модуля."""
    return get_logger("mtf.pipeline")


def get_integration_logger():
    """Логгер для Integration модуля."""
    return get_logger("mtf.integration")


def get_control_logger():
    """Логгер для Control модуля."""
    return get_logger("mtf.control")


def get_main_logger():
    """Основной логгер MTF."""
    return get_logger("mtf.main")


def get_mtf_logger(name: str = "mtf.main"):
    """Получение основного логгера MTF."""
    return get_logger(name)


# Context manager for logging
class LogContext:
    """Контекстный менеджер для логирования операций.

    DEPRECATED: Use src.logging.log_operation instead.
    """

    def __init__(
        self, module_name: str, operation: str, logger=None
    ):
        self.module_name = module_name
        self.operation = operation
        self.logger = logger or get_logger(module_name)
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting operation: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(
                f"Completed operation: {self.operation} in {duration:.3f}s"
            )
        else:
            self.logger.error(
                f"Failed operation: {self.operation} in {duration:.3f}s - {exc_val}"
            )


def create_log_context(module_name: str, operation_name: str, **kwargs):
    """Контекстный менеджер для логирования операций."""
    return LogContext(module_name, operation_name)


# Re-export for compatibility
__all__ = [
    "LogContext",
    "MTFLogger",
    "create_log_context",
    "get_consensus_logger",
    "get_context_logger",
    "get_control_logger",
    "get_integration_logger",
    "get_main_logger",
    "get_mtf_logger",
    "get_pipeline_logger",
    "get_triggers_logger",
    "setup_logging",
]
