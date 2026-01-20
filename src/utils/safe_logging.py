"""
Утилиты для безопасного логирования
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class SensitiveDataFilter(logging.Filter):
    """Фильтр для скрытия чувствительных данных в логах"""

    def __init__(self):
        super().__init__()
        # Паттерны для чувствительных данных
        self.sensitive_patterns = [
            r'password["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
            r'api_key["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
            r'secret["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
            r'token["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
            r'key["\']?\s*[:=]\s*["\']?[^"\s]+["\']?',
        ]

        # Компилируем паттерны для производительности
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.sensitive_patterns
        ]

    def filter(self, record):
        """Фильтрует чувствительные данные из сообщения лога"""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = self._sanitize_message(record.msg)

        if hasattr(record, "args") and record.args:
            record.args = tuple(self._sanitize_arg(arg) for arg in record.args)

        return True

    def _sanitize_message(self, message: str) -> str:
        """Очищает сообщение от чувствительных данных"""
        for pattern in self.compiled_patterns:
            message = pattern.sub(r"***HIDDEN***", message)
        return message

    def _sanitize_arg(self, arg: Any) -> Any:
        """Очищает аргументы от чувствительных данных"""
        if isinstance(arg, str):
            return self._sanitize_message(arg)
        if isinstance(arg, dict):
            return self._sanitize_dict(arg)
        if isinstance(arg, list):
            return [self._sanitize_arg(item) for item in arg]
        return arg

    def _sanitize_dict(self, data: dict) -> dict:
        """Очищает словарь от чувствительных данных"""
        sensitive_keys = ["password", "api_key", "secret", "token", "key"]
        sanitized = {}

        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***HIDDEN***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_arg(item) for item in value]
            else:
                sanitized[key] = value

        return sanitized


def setup_safe_logging(
    level: str = "INFO",
    log_file: str | None = None,
    format_string: str | None = None,
) -> logging.Logger:
    """
    Настраивает безопасное логирование

    Args:
        level: Уровень логирования
        log_file: Путь к файлу лога (опционально)
        format_string: Формат сообщений лога

    Returns:
        logging.Logger: Настроенный логгер
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Создаем форматтер
    formatter = logging.Formatter(format_string)

    # Создаем обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())

    # Создаем обработчик для файла (если указан)
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        handlers.append(file_handler)

    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Очищаем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Добавляем новые обработчики
    for handler in handlers:
        root_logger.addHandler(handler)

    return root_logger


def log_function_call(
    func_name: str, args: tuple | None = None, kwargs: dict | None = None
):
    """
    Декоратор для логирования вызовов функций

    Args:
        func_name: Имя функции
        args: Аргументы функции
        kwargs: Именованные аргументы функции
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Вызов функции {func_name} с аргументами: {args}, {kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Функция {func_name} завершена успешно")
                return result
            except Exception as e:
                logger.error(f"Ошибка в функции {func_name}: {e}")
                raise

        return wrapper

    return decorator


def log_database_operation(operation: str, table: str, **kwargs):
    """
    Логирует операции с базой данных

    Args:
        operation: Тип операции (SELECT, INSERT, UPDATE, DELETE)
        table: Имя таблицы
        **kwargs: Дополнительные параметры
    """
    context = f"Таблица: {table}"
    if kwargs:
        context += f", Параметры: {kwargs}"

    logger.info(f"Операция БД: {operation} - {context}")


def log_api_request(method: str, url: str, status_code: int | None = None, **kwargs):
    """
    Логирует API запросы

    Args:
        method: HTTP метод
        url: URL запроса
        status_code: Код ответа
        **kwargs: Дополнительные параметры
    """
    context = f"URL: {url}"
    if status_code:
        context += f", Статус: {status_code}"
    if kwargs:
        context += f", Параметры: {kwargs}"

    logger.info(f"API запрос: {method} - {context}")
