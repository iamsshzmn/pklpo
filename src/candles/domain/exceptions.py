"""
Иерархия исключений для модуля market_meta.

Предоставляет специфичные исключения для различных типов ошибок,
встречающихся в модуле market_meta.
"""

from typing import Any


class MarketMetaError(Exception):
    """
    Базовое исключение модуля market_meta.

    Все исключения модуля должны наследоваться от этого класса.
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (context: {context_str})"
        return self.message


class MetadataError(MarketMetaError):
    """Базовое исключение для ошибок, связанных с метаданными"""

    pass


class MetadataStaleError(MetadataError):
    """
    Метаданные устарели или недоступны.

    Возникает когда:
    - Кэш метаданных истек
    - Не удалось обновить метаданные
    - Метаданные повреждены
    """

    def __init__(
        self,
        message: str = "Метаданные устарели",
        last_refresh: str | None = None,
        ttl_hours: float | None = None,
    ):
        context = {}
        if last_refresh:
            context["last_refresh"] = last_refresh
        if ttl_hours:
            context["ttl_hours"] = ttl_hours
        super().__init__(message, context)


class MetadataNotFoundError(MetadataError):
    """
    Запрашиваемые метаданные не найдены.

    Возникает когда:
    - Инструмент не существует
    - Инструмент не торгуется
    - Инструмент удален
    """

    def __init__(self, symbol: str, message: str | None = None):
        if message is None:
            message = f"Метаданные для инструмента {symbol} не найдены"
        super().__init__(message, {"symbol": symbol})


class ValidationError(MarketMetaError):
    """
    Ошибка валидации данных.

    Базовое исключение для всех ошибок валидации.
    """

    def __init__(
        self,
        message: str,
        violations: list[str] | None = None,
        warnings: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context: dict[str, Any] = context.copy() if context else {}
        if violations:
            merged_context["violations"] = violations
        if warnings:
            merged_context["warnings"] = warnings
        super().__init__(message, merged_context)


class OrderValidationError(ValidationError):
    """
    Ошибка валидации ордера.

    Возникает при проверке параметров ордера:
    - Неверная цена
    - Неверное количество
    - Превышение лимитов
    """

    def __init__(
        self, symbol: str, violations: list[str], warnings: list[str] | None = None
    ):
        count = len(violations)
        plural = "нарушение" if count == 1 else "нарушения"
        message = f"Ошибка валидации ордера для {symbol}: {count} {plural}"
        super().__init__(message, violations, warnings, context={"symbol": symbol})
        self.symbol = symbol


class PriceValidationError(ValidationError):
    """
    Ошибка валидации цены.

    Возникает когда:
    - Цена не соответствует размеру тика
    - Цена вне допустимого диапазона
    - Цена равна нулю или отрицательная
    """

    def __init__(self, symbol: str, price: float, reason: str):
        message = f"Неверная цена {price} для {symbol}: {reason}"
        super().__init__(
            message,
            context={"symbol": symbol, "price": price, "reason": reason},
        )


class QuantityValidationError(ValidationError):
    """
    Ошибка валидации количества.

    Возникает когда:
    - Количество меньше минимального
    - Количество больше максимального
    - Количество не соответствует размеру лота
    """

    def __init__(self, symbol: str, quantity: float, reason: str):
        message = f"Неверное количество {quantity} для {symbol}: {reason}"
        super().__init__(
            message,
            context={"symbol": symbol, "quantity": quantity, "reason": reason},
        )


class RiskError(MarketMetaError):
    """Базовое исключение для ошибок, связанных с рисками"""

    pass


class RiskLimitBreach(RiskError):
    """
    Превышен лимит риска.

    Возникает когда:
    - Превышен лимит позиции
    - Превышена общая экспозиция
    - Превышен дневной лимит убытков
    """

    def __init__(
        self,
        message: str,
        risk_type: str,
        current_value: float | None = None,
        limit_value: float | None = None,
    ):
        context = {"risk_type": risk_type}
        if current_value is not None:
            context["current_value"] = current_value
        if limit_value is not None:
            context["limit_value"] = limit_value
        super().__init__(message, context)


class PositionLimitBreach(RiskLimitBreach):
    """
    Превышен лимит позиции для конкретного инструмента.
    """

    def __init__(self, symbol: str, quantity: float, max_quantity: float):
        message = f"Превышен лимит позиции для {symbol}: {quantity} > {max_quantity}"
        super().__init__(message, "position_limit", quantity, max_quantity)
        self.symbol = symbol


class ExposureLimitBreach(RiskLimitBreach):
    """
    Превышена общая экспозиция аккаунта.
    """

    def __init__(self, current_exposure: float, max_exposure: float):
        message = f"Превышена общая экспозиция: {current_exposure} > {max_exposure}"
        super().__init__(message, "total_exposure", current_exposure, max_exposure)


class IntegrationError(MarketMetaError):
    """Базовое исключение для ошибок интеграции с внешними системами"""

    pass


class OKXIntegrationError(IntegrationError):
    """
    Ошибка интеграции с OKX API.

    Возникает при:
    - Ошибках сети
    - Ошибках API (4xx, 5xx)
    - Превышении лимитов запросов
    - Неверных ответах API
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        endpoint: str | None = None,
        response_data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context: dict[str, Any] = dict(context) if context else {}
        if status_code is not None:
            merged_context["status_code"] = status_code
        if endpoint:
            merged_context["endpoint"] = endpoint
        if response_data:
            merged_context["response_data"] = response_data
        super().__init__(message, merged_context)


class OKXRateLimitError(OKXIntegrationError):
    """
    Превышен лимит запросов к OKX API.
    """

    def __init__(
        self, retry_after: int | None = None, context: dict[str, Any] | None = None
    ):
        message = "Превышен лимит запросов к OKX API"
        merged_context = dict(context) if context else {}
        if retry_after is not None:
            merged_context["retry_after"] = retry_after
        super().__init__(message, context=merged_context)


class OKXNetworkError(OKXIntegrationError):
    """
    Ошибка сети при обращении к OKX API.
    """

    def __init__(
        self,
        original_error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ):
        message = "Ошибка сети при обращении к OKX API"
        merged_context = dict(context) if context else {}
        if original_error:
            merged_context["original_error"] = str(original_error)
        super().__init__(message, context=merged_context)


class ConfigurationError(MarketMetaError):
    """
    Ошибка конфигурации модуля.

    Возникает при:
    - Отсутствии обязательных параметров
    - Неверных значениях конфигурации
    - Конфликтах в настройках
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        config_value: Any | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context: dict[str, Any] = {}
        if config_key is not None:
            merged_context["config_key"] = config_key
        if config_value is not None:
            merged_context["config_value"] = config_value
        if context:
            merged_context.update(context)
        super().__init__(message, merged_context)


class CacheError(MarketMetaError):
    """Базовое исключение для ошибок кэширования"""

    pass


class CacheCorruptionError(CacheError):
    """
    Ошибка повреждения кэша.

    Возникает когда:
    - Данные кэша повреждены
    - Неверный формат данных
    - Ошибка десериализации
    """

    def __init__(self, message: str, cache_key: str | None = None):
        context = {}
        if cache_key:
            context["cache_key"] = cache_key
        super().__init__(message, context)


# Утилитарные функции для работы с исключениями


def is_retryable_error(error: Exception) -> bool:
    """
    Проверяет, является ли ошибка повторяемой.

    Args:
        error: Исключение для проверки

    Returns:
        True если ошибку можно повторить
    """
    if isinstance(error, OKXNetworkError):
        return True
    if isinstance(error, OKXRateLimitError):
        return True
    return bool(isinstance(error, MetadataStaleError))


def get_error_context(error: MarketMetaError) -> dict[str, Any]:
    """
    Получает контекст ошибки.

    Args:
        error: Исключение модуля market_meta

    Returns:
        Словарь с контекстом ошибки
    """
    return error.context.copy()


def format_error_message(error: MarketMetaError) -> str:
    """
    Форматирует сообщение об ошибке с контекстом.

    Args:
        error: Исключение модуля market_meta

    Returns:
        Отформатированное сообщение об ошибке
    """
    if error.context:
        context_parts = []
        for key, value in error.context.items():
            if isinstance(value, list | dict):
                context_parts.append(f"{key}={type(value).__name__}")
            else:
                context_parts.append(f"{key}={value}")
        return f"{error.message} [{', '.join(context_parts)}]"
    return error.message
