"""
Централизованная конфигурация логирования для модуля market_meta.

Обеспечивает:
- Единый формат логов
- Настраиваемые уровни для разных компонентов
- Ротацию файлов
- Структурированное логирование
- Дочерний логгер от root (не создаёт дублирующую конфигурацию)
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Any

# Константа имени логгера сервиса
LOGGER_NAME = "market_meta"

# Константы для логирования
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DEFAULT_LOG_FILE = "/opt/airflow/project/logs/market_meta.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


class MarketMetaLogger:
    """
    Централизованный логгер для модуля market_meta.

    Создаёт дочерний логгер от root, не переопределяя глобальную конфигурацию.
    """

    def __init__(self, name: str = LOGGER_NAME):
        self.name = name
        # Создаём дочерний логгер от root
        self.logger = logging.getLogger(name)
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
        """
        Настраивает логирование для модуля.

        Создаёт дочерний логгер от root, не переопределяя глобальную конфигурацию.

        Args:
            level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Путь к файлу логов (если None, используется DEFAULT_LOG_FILE)
            log_format: Формат логов
            console_output: Выводить ли логи в консоль
            file_output: Записывать ли логи в файл
            max_size: Максимальный размер файла логов в байтах
            backup_count: Количество файлов ротации
        """
        if self._configured:
            return

        # Устанавливаем уровень логирования
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.setLevel(log_level)

        # Не очищаем обработчики root - работаем как дочерний логгер
        # Если root уже настроен, используем его конфигурацию
        # Если нет - добавляем свои обработчики только для этого логгера

        # Проверяем, есть ли уже обработчики у root
        root_logger = logging.getLogger()
        has_root_handlers = root_logger.hasHandlers()

        # Создаем форматтер
        formatter = logging.Formatter(log_format)

        # Всегда добавляем обработчики для дочернего логгера, если они запрошены
        # Это позволяет тестам работать независимо от конфигурации root
        handlers_added = False

        # Консольный обработчик
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            handlers_added = True

        # Файловый обработчик с ротацией
        if file_output:
            if log_file is None:
                log_file = DEFAULT_LOG_FILE

            # Создаем директорию для логов если её нет
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            handlers_added = True

        # Устанавливаем propagate=True чтобы логи шли в root (если root настроен)
        # или propagate=False если мы сами настраиваем обработчики
        self.logger.propagate = has_root_handlers and not handlers_added

        self._configured = True
        if handlers_added:
            self.logger.info(
                f"Логирование настроено для {self.name} (уровень: {level})"
            )

    def get_logger(self, name: str | None = None) -> logging.Logger:
        """
        Возвращает логгер для указанного компонента.

        Args:
            name: Имя компонента (если None, возвращает основной логгер)

        Returns:
            Настроенный логгер
        """
        if name:
            return logging.getLogger(f"{self.name}.{name}")
        return self.logger

    def log_validation_result(
        self, symbol: str, violations: list[str], warnings: list[str] | None = None
    ) -> None:
        """
        Логирует результат валидации ордера.

        Args:
            symbol: Символ инструмента
            violations: Список нарушений
            warnings: Список предупреждений
        """
        if violations:
            count = len(violations)
            # Правильное множественное число: 1 нарушение, 2-4 нарушения, 5+ нарушений
            if count == 1:
                violation_word = "нарушение"
            elif 2 <= count <= 4:
                violation_word = "нарушения"
            else:
                violation_word = "нарушений"
            self.logger.warning(
                f"Валидация ордера {symbol} не прошла: {count} {violation_word}"
            )
            for i, violation in enumerate(violations, 1):
                self.logger.warning(f"  {i}. {violation}")
        else:
            self.logger.info(f"Валидация ордера {symbol} прошла успешно")

        if warnings:
            for warning in warnings:
                self.logger.info(f"Предупреждение для {symbol}: {warning}")

    def log_cache_status(self, status: dict[str, Any]) -> None:
        """
        Логирует статус кэша.

        Args:
            status: Словарь со статусом кэша
        """
        self.logger.info(
            f"Статус кэша: актуален={status.get('is_valid')}, "
            f"инструментов={status.get('instruments_count')}, "
            f"TTL={status.get('ttl_hours', 0):.1f}ч"
        )

    def log_refresh_status(
        self, success: bool, instruments_count: int = 0, error: str | None = None
    ) -> None:
        """
        Логирует статус обновления метаданных.

        Args:
            success: Успешность обновления
            instruments_count: Количество загруженных инструментов
            error: Сообщение об ошибке
        """
        if success:
            self.logger.info(
                f"Обновление метаданных успешно завершено: {instruments_count} инструментов"
            )
        else:
            self.logger.error(f"Ошибка обновления метаданных: {error}")

    def log_risk_check(self, symbol: str, risk_level: str, details: str) -> None:
        """
        Логирует проверку рисков.

        Args:
            symbol: Символ инструмента
            risk_level: Уровень риска
            details: Детали проверки
        """
        if risk_level.upper() in ["HIGH", "CRITICAL"]:
            self.logger.warning(f"Высокий риск для {symbol}: {details}")
        else:
            self.logger.info(f"Проверка рисков {symbol}: {details}")


# Глобальный экземпляр логгера
_market_meta_logger = MarketMetaLogger()


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Возвращает настроенный логгер для модуля market_meta.

    Создаёт дочерний логгер от LOGGER_NAME, который является дочерним от root.

    Args:
        name: Имя компонента (например, "api", "validators")
               Если None, возвращает основной логгер сервиса

    Returns:
        Настроенный логгер (дочерний от LOGGER_NAME)

    Examples:
        >>> logger = get_logger()  # Возвращает логгер "market_meta"
        >>> api_logger = get_logger("api")  # Возвращает логгер "market_meta.api"
    """
    if name:
        # Создаём дочерний логгер: market_meta.api, market_meta.validators и т.д.
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    # Возвращаем основной логгер сервиса
    return _market_meta_logger.get_logger()


def configure_logging(**kwargs) -> None:
    """
    Настраивает логирование для модуля market_meta.

    Args:
        **kwargs: Параметры конфигурации (см. MarketMetaLogger.configure)
    """
    _market_meta_logger.configure(**kwargs)


def log_validation_result(
    symbol: str, violations: list[str], warnings: list[str] | None = None
) -> None:
    """Логирует результат валидации ордера"""
    _market_meta_logger.log_validation_result(symbol, violations, warnings)


def log_cache_status(status: dict[str, Any]) -> None:
    """Логирует статус кэша"""
    _market_meta_logger.log_cache_status(status)


def log_refresh_status(
    success: bool, instruments_count: int = 0, error: str | None = None
) -> None:
    """Логирует статус обновления метаданных"""
    _market_meta_logger.log_refresh_status(success, instruments_count, error)


def log_risk_check(symbol: str, risk_level: str, details: str) -> None:
    """Логирует проверку рисков"""
    _market_meta_logger.log_risk_check(symbol, risk_level, details)


# Автоматическая настройка при импорте
def auto_configure() -> None:
    """Автоматическая настройка логирования из переменных окружения"""
    level = os.getenv("MARKET_META_LOG_LEVEL", DEFAULT_LOG_LEVEL)
    log_file = os.getenv("MARKET_META_LOG_FILE", DEFAULT_LOG_FILE)
    console_output = os.getenv("MARKET_META_CONSOLE_LOG", "true").lower() == "true"
    file_output = os.getenv("MARKET_META_FILE_LOG", "true").lower() == "true"

    configure_logging(
        level=level,
        log_file=log_file,
        console_output=console_output,
        file_output=file_output,
    )


# Настраиваем логирование при импорте модуля
auto_configure()
