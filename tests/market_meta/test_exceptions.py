"""
Тесты для иерархии исключений модуля market_meta.
"""

import pytest

from src.market_meta.domain.exceptions import (
    CacheCorruptionError,
    CacheError,
    ConfigurationError,
    ExposureLimitBreach,
    IntegrationError,
    MarketMetaError,
    MetadataError,
    MetadataNotFoundError,
    MetadataStaleError,
    OKXIntegrationError,
    OKXNetworkError,
    OKXRateLimitError,
    OrderValidationError,
    PositionLimitBreach,
    PriceValidationError,
    QuantityValidationError,
    RiskError,
    RiskLimitBreach,
    ValidationError,
    format_error_message,
    get_error_context,
    is_retryable_error,
)


class TestMarketMetaError:
    """Тесты базового исключения"""

    def test_basic_error(self):
        """Тест базового исключения без контекста"""
        error = MarketMetaError("Тестовая ошибка")
        assert str(error) == "Тестовая ошибка"
        assert error.message == "Тестовая ошибка"
        assert error.context == {}

    def test_error_with_context(self):
        """Тест исключения с контекстом"""
        context = {"symbol": "BTC-USDT", "price": 50000}
        error = MarketMetaError("Ошибка валидации", context)
        assert "Тестовая ошибка" not in str(error)
        assert "symbol=BTC-USDT" in str(error)
        assert "price=50000" in str(error)
        assert error.context == context

    def test_error_inheritance(self):
        """Тест наследования от Exception"""
        error = MarketMetaError("Тест")
        assert isinstance(error, Exception)
        assert isinstance(error, MarketMetaError)


class TestMetadataErrors:
    """Тесты исключений метаданных"""

    def test_metadata_stale_error(self):
        """Тест исключения устаревших метаданных"""
        error = MetadataStaleError(
            "Метаданные устарели", last_refresh="2023-01-01T00:00:00", ttl_hours=2.5
        )
        assert "last_refresh" in error.context
        assert "ttl_hours" in error.context
        assert error.context["last_refresh"] == "2023-01-01T00:00:00"
        assert error.context["ttl_hours"] == 2.5

    def test_metadata_not_found_error(self):
        """Тест исключения отсутствующих метаданных"""
        error = MetadataNotFoundError("BTC-USDT")
        assert error.context["symbol"] == "BTC-USDT"
        assert "BTC-USDT" in str(error)

    def test_metadata_inheritance(self):
        """Тест наследования исключений метаданных"""
        stale_error = MetadataStaleError()
        not_found_error = MetadataNotFoundError("BTC-USDT")

        assert isinstance(stale_error, MetadataError)
        assert isinstance(not_found_error, MetadataError)
        assert isinstance(stale_error, MarketMetaError)
        assert isinstance(not_found_error, MarketMetaError)


class TestValidationErrors:
    """Тесты исключений валидации"""

    def test_validation_error(self):
        """Тест базового исключения валидации"""
        violations = ["Цена неверная", "Количество превышает лимит"]
        warnings = ["Рекомендуется проверить баланс"]

        error = ValidationError(
            "Ошибка валидации", violations=violations, warnings=warnings
        )

        assert error.context["violations"] == violations
        assert error.context["warnings"] == warnings

    def test_order_validation_error(self):
        """Тест исключения валидации ордера"""
        violations = ["Цена неверная", "Количество превышает лимит"]
        error = OrderValidationError("BTC-USDT", violations)

        assert error.symbol == "BTC-USDT"
        assert error.context["violations"] == violations
        assert "2 нарушения" in str(error)

    def test_price_validation_error(self):
        """Тест исключения валидации цены"""
        error = PriceValidationError(
            "BTC-USDT", 50000, "Цена не соответствует размеру тика"
        )

        assert error.context["symbol"] == "BTC-USDT"
        assert error.context["price"] == 50000
        assert error.context["reason"] == "Цена не соответствует размеру тика"
        assert "50000" in str(error)

    def test_quantity_validation_error(self):
        """Тест исключения валидации количества"""
        error = QuantityValidationError(
            "BTC-USDT", 1000, "Количество превышает максимальное"
        )

        assert error.context["symbol"] == "BTC-USDT"
        assert error.context["quantity"] == 1000
        assert error.context["reason"] == "Количество превышает максимальное"
        assert "1000" in str(error)

    def test_validation_inheritance(self):
        """Тест наследования исключений валидации"""
        validation_error = ValidationError("Тест")
        order_error = OrderValidationError("BTC-USDT", [])
        price_error = PriceValidationError("BTC-USDT", 100, "Тест")

        assert isinstance(validation_error, MarketMetaError)
        assert isinstance(order_error, ValidationError)
        assert isinstance(price_error, ValidationError)


class TestRiskErrors:
    """Тесты исключений рисков"""

    def test_risk_limit_breach(self):
        """Тест базового исключения превышения лимита риска"""
        error = RiskLimitBreach(
            "Превышен лимит", "position_limit", current_value=1000, limit_value=500
        )

        assert error.context["risk_type"] == "position_limit"
        assert error.context["current_value"] == 1000
        assert error.context["limit_value"] == 500

    def test_position_limit_breach(self):
        """Тест исключения превышения лимита позиции"""
        error = PositionLimitBreach("BTC-USDT", 1000, 500)

        assert error.symbol == "BTC-USDT"
        assert error.context["current_value"] == 1000
        assert error.context["limit_value"] == 500
        assert "1000 > 500" in str(error)

    def test_exposure_limit_breach(self):
        """Тест исключения превышения общей экспозиции"""
        error = ExposureLimitBreach(10000, 5000)

        assert error.context["current_value"] == 10000
        assert error.context["limit_value"] == 5000
        assert "10000 > 5000" in str(error)

    def test_risk_inheritance(self):
        """Тест наследования исключений рисков"""
        risk_error = RiskLimitBreach("Тест", "test")
        position_error = PositionLimitBreach("BTC-USDT", 100, 50)
        exposure_error = ExposureLimitBreach(1000, 500)

        assert isinstance(risk_error, RiskError)
        assert isinstance(position_error, RiskLimitBreach)
        assert isinstance(exposure_error, RiskLimitBreach)
        assert isinstance(risk_error, MarketMetaError)


class TestIntegrationErrors:
    """Тесты исключений интеграции"""

    def test_okx_integration_error(self):
        """Тест базового исключения интеграции с OKX"""
        error = OKXIntegrationError(
            "Ошибка API",
            status_code=429,
            endpoint="/api/v5/public/instruments",
            response_data={"code": "429", "msg": "Rate limit exceeded"},
        )

        assert error.context["status_code"] == 429
        assert error.context["endpoint"] == "/api/v5/public/instruments"
        assert error.context["response_data"]["code"] == "429"

    def test_okx_rate_limit_error(self):
        """Тест исключения превышения лимита запросов"""
        error = OKXRateLimitError(retry_after=60)

        assert error.context["retry_after"] == 60
        assert "лимит запросов" in str(error)

    def test_okx_network_error(self):
        """Тест исключения сетевой ошибки"""
        original_error = ConnectionError("Connection refused")
        error = OKXNetworkError(original_error)

        assert "Connection refused" in error.context["original_error"]
        assert "сети" in str(error)

    def test_integration_inheritance(self):
        """Тест наследования исключений интеграции"""
        integration_error = OKXIntegrationError("Тест")
        rate_limit_error = OKXRateLimitError()
        network_error = OKXNetworkError()

        assert isinstance(integration_error, IntegrationError)
        assert isinstance(rate_limit_error, OKXIntegrationError)
        assert isinstance(network_error, OKXIntegrationError)
        assert isinstance(integration_error, MarketMetaError)


class TestConfigurationErrors:
    """Тесты исключений конфигурации"""

    def test_configuration_error(self):
        """Тест исключения конфигурации"""
        error = ConfigurationError(
            "Неверное значение", config_key="cache_ttl", config_value=-1
        )

        assert error.context["config_key"] == "cache_ttl"
        assert error.context["config_value"] == -1

    def test_configuration_inheritance(self):
        """Тест наследования исключения конфигурации"""
        error = ConfigurationError("Тест")
        assert isinstance(error, MarketMetaError)


class TestCacheErrors:
    """Тесты исключений кэша"""

    def test_cache_corruption_error(self):
        """Тест исключения повреждения кэша"""
        error = CacheCorruptionError("Данные повреждены", cache_key="market_metadata")

        assert error.context["cache_key"] == "market_metadata"

    def test_cache_inheritance(self):
        """Тест наследования исключений кэша"""
        error = CacheCorruptionError("Тест")
        assert isinstance(error, CacheError)
        assert isinstance(error, MarketMetaError)


class TestUtilityFunctions:
    """Тесты утилитарных функций"""

    def test_is_retryable_error(self):
        """Тест функции проверки повторяемости ошибки"""
        # Повторяемые ошибки
        assert is_retryable_error(OKXNetworkError())
        assert is_retryable_error(OKXRateLimitError())
        assert is_retryable_error(MetadataStaleError())

        # Неповторяемые ошибки
        assert not is_retryable_error(ValidationError("Тест"))
        assert not is_retryable_error(RiskLimitBreach("Тест", "test"))
        assert not is_retryable_error(ValueError("Тест"))

    def test_get_error_context(self):
        """Тест функции получения контекста ошибки"""
        context = {"symbol": "BTC-USDT", "price": 50000}
        error = MarketMetaError("Тест", context)

        retrieved_context = get_error_context(error)
        assert retrieved_context == context
        assert retrieved_context is not error.context  # Копия, не ссылка

    def test_format_error_message(self):
        """Тест функции форматирования сообщения об ошибке"""
        context = {"symbol": "BTC-USDT", "price": 50000}
        error = MarketMetaError("Ошибка валидации", context)

        formatted = format_error_message(error)
        assert "Ошибка валидации" in formatted
        assert "symbol=BTC-USDT" in formatted
        assert "price=50000" in formatted

    def test_format_error_message_with_complex_context(self):
        """Тест форматирования с комплексным контекстом"""
        context = {
            "violations": ["Ошибка 1", "Ошибка 2"],
            "warnings": ["Предупреждение"],
            "simple_value": 123,
        }
        error = MarketMetaError("Тест", context)

        formatted = format_error_message(error)
        assert "violations=list" in formatted
        assert "warnings=list" in formatted
        assert "simple_value=123" in formatted


class TestErrorHierarchy:
    """Тесты иерархии исключений"""

    def test_error_hierarchy(self):
        """Тест правильности иерархии исключений"""
        # Проверяем, что все исключения наследуются от MarketMetaError
        errors = [
            MetadataStaleError(),
            ValidationError("Тест"),
            RiskLimitBreach("Тест", "test"),
            OKXIntegrationError("Тест"),
            ConfigurationError("Тест"),
            CacheCorruptionError("Тест"),
        ]

        for error in errors:
            assert isinstance(error, MarketMetaError)

    def test_specific_error_types(self):
        """Тест специфичности типов исключений"""
        # Проверяем, что исключения имеют правильные типы
        assert isinstance(MetadataStaleError(), MetadataError)
        assert isinstance(OrderValidationError("BTC", []), ValidationError)
        assert isinstance(PositionLimitBreach("BTC", 100, 50), RiskLimitBreach)
        assert isinstance(OKXRateLimitError(), OKXIntegrationError)

    def test_error_context_preservation(self):
        """Тест сохранения контекста в иерархии"""
        # Создаем исключение с контекстом
        context = {"test_key": "test_value"}
        error = MarketMetaError("Тест", context)

        # Проверяем, что контекст сохраняется
        assert error.context == context
        assert "test_key" in error.context
        assert error.context["test_key"] == "test_value"


if __name__ == "__main__":
    pytest.main([__file__])
