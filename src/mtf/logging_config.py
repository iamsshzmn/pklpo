"""
Централизованная система логирования для MTF модулей
"""

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any


class MTFLogger:
    """Централизованный логгер для MTF системы"""

    _loggers: dict[str, logging.Logger] = {}
    _initialized = False

    @classmethod
    def initialize(cls, log_dir: str = "logs/mtf", log_level: str = "INFO"):
        """Инициализация системы логирования"""
        if cls._initialized:
            return

        # Создание директории для логов
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Настройка базовой конфигурации
        cls._setup_logging(log_path, log_level)
        cls._initialized = True

        # Логирование инициализации
        main_logger = cls.get_logger("mtf.main")
        main_logger.info(
            f"MTF Logging system initialized. Log directory: {log_path.absolute()}"
        )

    @classmethod
    def _setup_logging(cls, log_path: Path, log_level: str):
        """Настройка базовой конфигурации логирования"""
        # Уровень логирования
        level = getattr(logging, log_level.upper(), logging.INFO)

        # Формат логов
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Обработчик для консоли
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)

        # Обработчик для основного файла
        main_file_handler = logging.handlers.RotatingFileHandler(
            log_path / "mtf_main.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,  # 10MB
        )
        main_file_handler.setLevel(level)
        main_file_handler.setFormatter(formatter)

        # Обработчик для ошибок
        error_file_handler = logging.handlers.RotatingFileHandler(
            log_path / "mtf_errors.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(formatter)

        # Настройка корневого логгера
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(main_file_handler)
        root_logger.addHandler(error_file_handler)

    @classmethod
    def get_logger(cls, module_name: str) -> logging.Logger:
        """Получение логгера для модуля"""
        if not cls._initialized:
            cls.initialize()

        if module_name not in cls._loggers:
            logger = logging.getLogger(f"mtf.{module_name}")

            # Добавление специфичного обработчика для модуля
            cls._add_module_handler(logger, module_name)

            cls._loggers[module_name] = logger

        return cls._loggers[module_name]

    @classmethod
    def _add_module_handler(cls, logger: logging.Logger, module_name: str):
        """Добавление специфичного обработчика для модуля"""
        log_path = Path("logs/mtf")

        # Файл для модуля
        module_file_handler = logging.handlers.RotatingFileHandler(
            log_path / f"mtf_{module_name}.log",
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
        )
        module_file_handler.setLevel(logging.DEBUG)

        # Формат для модуля
        module_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        module_file_handler.setFormatter(module_formatter)

        logger.addHandler(module_file_handler)
        logger.propagate = True  # Пропускаем в корневой логгер

    @classmethod
    def log_performance(
        cls,
        module_name: str,
        operation: str,
        duration: float,
        metadata: dict[str, Any] | None = None,
    ):
        """Логирование производительности"""
        logger = cls.get_logger(f"{module_name}.performance")

        {
            "operation": operation,
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        logger.info(
            f"PERFORMANCE | {operation} | {duration:.3f}s | {json.dumps(metadata or {})}"
        )

    @classmethod
    def log_error(
        cls,
        module_name: str,
        error: Exception,
        context: dict[str, Any] | None = None,
    ):
        """Логирование ошибок с контекстом"""
        logger = cls.get_logger(f"{module_name}.errors")

        {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
        }

        logger.error(
            f"ERROR | {type(error).__name__} | {error!s} | {json.dumps(context or {})}"
        )

    @classmethod
    def log_metrics(cls, module_name: str, metrics: dict[str, Any]):
        """Логирование метрик"""
        logger = cls.get_logger(f"{module_name}.metrics")

        {"timestamp": datetime.now().isoformat(), "metrics": metrics}

        logger.info(f"METRICS | {json.dumps(metrics)}")

    @classmethod
    def get_log_files(cls) -> dict[str, Path]:
        """Получение списка файлов логов"""
        log_path = Path("logs/mtf")
        log_files = {}

        if log_path.exists():
            for log_file in log_path.glob("*.log"):
                log_files[log_file.stem] = log_file

        return log_files

    @classmethod
    def cleanup_old_logs(cls, days: int = 30):
        """Очистка старых логов"""
        log_path = Path("logs/mtf")
        if not log_path.exists():
            return

        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)

        for log_file in log_path.glob("*.log*"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                cls.get_logger("mtf.main").info(f"Removed old log file: {log_file}")


# Предустановленные логгеры для модулей
def get_context_logger() -> logging.Logger:
    """Логгер для Context модуля"""
    return MTFLogger.get_logger("context")


def get_triggers_logger() -> logging.Logger:
    """Логгер для Triggers модуля"""
    return MTFLogger.get_logger("triggers")


def get_consensus_logger() -> logging.Logger:
    """Логгер для Consensus модуля"""
    return MTFLogger.get_logger("consensus")


def get_pipeline_logger() -> logging.Logger:
    """Логгер для Pipeline модуля"""
    return MTFLogger.get_logger("pipeline")


def get_integration_logger() -> logging.Logger:
    """Логгер для Integration модуля"""
    return MTFLogger.get_logger("integration")


def get_main_logger() -> logging.Logger:
    """Основной логгер MTF"""
    return MTFLogger.get_logger("main")


# Декоратор для логирования производительности
def log_performance(module_name: str, operation_name: str | None = None):
    """Декоратор для автоматического логирования производительности"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            operation = operation_name or func.__name__

            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()

                MTFLogger.log_performance(
                    module_name,
                    operation,
                    duration,
                    {
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_count": len(kwargs),
                    },
                )

                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()

                MTFLogger.log_error(
                    module_name,
                    e,
                    {
                        "function": func.__name__,
                        "operation": operation,
                        "duration": duration,
                    },
                )

                raise

        return wrapper

    return decorator


# Контекстный менеджер для логирования
class LogContext:
    """Контекстный менеджер для логирования операций"""

    def __init__(
        self, module_name: str, operation: str, logger: logging.Logger | None = None
    ):
        self.module_name = module_name
        self.operation = operation
        self.logger = logger or MTFLogger.get_logger(module_name)
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
            MTFLogger.log_performance(self.module_name, self.operation, duration)
        else:
            self.logger.error(
                f"Failed operation: {self.operation} in {duration:.3f}s - {exc_val}"
            )
            MTFLogger.log_error(
                self.module_name,
                exc_val,
                {"operation": self.operation, "duration": duration},
            )


# Функции-обертки для совместимости
def setup_logging(log_level: str = "INFO"):
    """Инициализация системы логирования"""
    MTFLogger.initialize(log_level=log_level)


def get_mtf_logger(name: str = "mtf.main"):
    """Получение основного логгера MTF"""
    return MTFLogger.get_logger(name)


def get_context_logger():
    """Получение логгера для Context модуля"""
    return MTFLogger.get_logger("mtf.context")


def get_triggers_logger():
    """Получение логгера для Triggers модуля"""
    return MTFLogger.get_logger("mtf.triggers")


def get_consensus_logger():
    """Получение логгера для Consensus модуля"""
    return MTFLogger.get_logger("mtf.consensus")


def get_pipeline_logger():
    """Получение логгера для Pipeline модуля"""
    return MTFLogger.get_logger("mtf.pipeline")


def get_integration_logger():
    """Получение логгера для Integration модуля"""
    return MTFLogger.get_logger("mtf.integration")


def get_control_logger():
    """Получение логгера для Control модуля"""
    return MTFLogger.get_logger("mtf.control")


def log_performance(module_name: str, operation_name: str):
    """Декоратор для логирования производительности"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            MTFLogger.log_performance(module_name, operation_name, duration)
            return result

        return wrapper

    return decorator


def create_log_context(module_name: str, operation_name: str, **kwargs):
    """Контекстный менеджер для логирования операций"""
    return LogContext(module_name, operation_name)


# Инициализация при импорте
MTFLogger.initialize()
