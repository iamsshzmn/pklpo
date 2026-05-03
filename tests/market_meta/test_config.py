"""
Тесты для системы конфигурации market_meta.
"""

import os
from unittest.mock import patch

import pytest

from src.market_meta_backup.domain.exceptions import ConfigurationError
from src.market_meta_backup.infrastructure.config import (
    CacheConfig,
    LoggingConfig,
    MarketMetaConfig,
    MetricsConfig,
    OKXConfig,
    RiskConfig,
    ValidationConfig,
    get_config,
    reload_config,
    set_config,
)


class TestOKXConfig:
    """Тесты конфигурации OKX"""

    def test_default_values(self):
        """Тест значений по умолчанию"""
        config = OKXConfig()

        assert config.api_key is None
        assert config.base_url == "https://www.okx.com"
        assert config.timeout_seconds == 30
        assert config.max_requests_per_second == 10
        assert config.max_retries == 3
        assert config.base_delay_seconds == 1.0
        assert config.max_delay_seconds == 60.0

    def test_validation_success(self):
        """Тест успешной валидации"""
        config = OKXConfig(
            timeout_seconds=60,
            max_requests_per_second=20,
            max_retries=5,
            base_delay_seconds=2.0,
        )

        errors = config.validate()
        assert len(errors) == 0

    def test_validation_errors(self):
        """Тест ошибок валидации"""
        config = OKXConfig(
            timeout_seconds=0,  # Ошибка
            max_requests_per_second=-1,  # Ошибка
            max_retries=-5,  # Ошибка
            base_delay_seconds=0.0,  # Ошибка
        )

        errors = config.validate()
        assert len(errors) == 4
        assert "OKX_TIMEOUT_SECONDS должен быть положительным" in errors
        assert "OKX_MAX_REQUESTS_PER_SECOND должен быть положительным" in errors
        assert "OKX_MAX_RETRIES не может быть отрицательным" in errors
        assert "OKX_BASE_DELAY_SECONDS должен быть положительным" in errors


class TestCacheConfig:
    """Тесты конфигурации кэша"""

    def test_default_values(self):
        """Тест значений по умолчанию"""
        config = CacheConfig()

        assert config.metadata_ttl_hours == 1
        assert config.auto_refresh_enabled is True
        assert config.auto_refresh_interval_hours == 1
        assert config.max_cache_size_mb == 100

    def test_validation_errors(self):
        """Тест ошибок валидации"""
        config = CacheConfig(
            metadata_ttl_hours=0,  # Ошибка
            auto_refresh_interval_hours=-1,  # Ошибка
            max_cache_size_mb=0,  # Ошибка
        )

        errors = config.validate()
        assert len(errors) == 3


class TestLoggingConfig:
    """Тесты конфигурации логирования"""

    def test_default_values(self):
        """Тест значений по умолчанию"""
        config = LoggingConfig()

        assert config.log_level == "INFO"
        assert config.log_format == "json"
        assert config.mask_api_keys is True
        assert config.max_message_length == 1000

    def test_validation_success(self):
        """Тест успешной валидации"""
        config = LoggingConfig(
            log_level="DEBUG", log_format="text", max_log_size_mb=20, backup_count=10
        )

        errors = config.validate()
        assert len(errors) == 0

    def test_validation_errors(self):
        """Тест ошибок валидации"""
        config = LoggingConfig(
            log_level="INVALID",  # Ошибка
            log_format="xml",  # Ошибка
            max_log_size_mb=0,  # Ошибка
            backup_count=-1,  # Ошибка
            max_message_length=0,  # Ошибка
        )

        errors = config.validate()
        assert len(errors) == 5


class TestValidationConfig:
    """Тесты конфигурации валидации"""

    def test_default_values(self):
        """Тест значений по умолчанию"""
        config = ValidationConfig()

        assert config.strict_mode is True
        assert config.allow_warnings is True
        assert config.validate_risk_limits is True
        assert config.validate_liquidity is False

    def test_validation_errors(self):
        """Тест ошибок валидации"""
        config = ValidationConfig(
            max_validation_errors=0,
            max_validation_warnings=-1,  # Ошибка  # Ошибка
        )

        errors = config.validate()
        assert len(errors) == 2


class TestRiskConfig:
    """Тесты конфигурации рисков"""

    def test_default_values(self):
        """Тест значений по умолчанию"""
        config = RiskConfig()

        assert config.max_position_size_usd == 10000.0
        assert config.max_total_exposure_usd == 50000.0
        assert config.max_leverage == 10
        assert config.risk_tolerance == "conservative"
        assert config.risk_alert_threshold == 0.8
        assert config.critical_risk_threshold == 0.95

    def test_validation_success(self):
        """Тест успешной валидации"""
        config = RiskConfig(
            max_position_size_usd=5000.0,
            max_total_exposure_usd=25000.0,
            max_leverage=5,
            risk_tolerance="moderate",
            risk_alert_threshold=0.7,
            critical_risk_threshold=0.9,
        )

        errors = config.validate()
        assert len(errors) == 0

    def test_validation_errors(self):
        """Тест ошибок валидации"""
        config = RiskConfig(
            max_position_size_usd=0.0,  # Ошибка
            max_total_exposure_usd=-1000.0,  # Ошибка
            max_leverage=0,  # Ошибка
            risk_tolerance="invalid",  # Ошибка
            risk_alert_threshold=1.5,  # Ошибка
            critical_risk_threshold=0.5,  # Ошибка (меньше alert threshold)
        )

        errors = config.validate()
        assert len(errors) == 6


class TestMetricsConfig:
    """Тесты конфигурации метрик"""

    def test_default_values(self):
        """Тест значений по умолчанию"""
        config = MetricsConfig()

        assert config.enabled is True
        assert config.export_metrics is False
        assert config.metrics_port == 9090
        assert config.metrics_retention_hours == 24

    def test_validation_errors(self):
        """Тест ошибок валидации"""
        config = MetricsConfig(
            metrics_port=0,  # Ошибка
            cache_metrics_interval_seconds=-1,  # Ошибка
            metrics_retention_hours=0,  # Ошибка
        )

        errors = config.validate()
        assert len(errors) == 3


class TestMarketMetaConfig:
    """Тесты основной конфигурации"""

    def test_default_values(self):
        """Тест значений по умолчанию"""
        config = MarketMetaConfig()

        assert config.environment == "development"
        assert config.debug_mode is False
        assert config.data_dir == "./data"
        assert isinstance(config.okx, OKXConfig)
        assert isinstance(config.cache, CacheConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.validation, ValidationConfig)
        assert isinstance(config.risk, RiskConfig)
        assert isinstance(config.metrics, MetricsConfig)

    def test_validation_success(self):
        """Тест успешной валидации"""
        config = MarketMetaConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validation_environment_error(self):
        """Тест ошибки валидации окружения"""
        config = MarketMetaConfig()
        config.environment = "invalid"

        errors = config.validate()
        assert len(errors) == 1
        assert "MARKET_META_ENVIRONMENT должен быть" in errors[0]

    def test_to_dict(self):
        """Тест преобразования в словарь"""
        config = MarketMetaConfig()
        config_dict = config.to_dict()

        assert "environment" in config_dict
        assert "okx" in config_dict
        assert "cache" in config_dict
        assert "logging" in config_dict
        assert "validation" in config_dict
        assert "risk" in config_dict
        assert "metrics" in config_dict

        # Проверяем маскировку API ключей
        assert config_dict["okx"]["api_key"] == "***"

    @patch.dict(
        os.environ,
        {
            "MARKET_META_ENVIRONMENT": "production",
            "MARKET_META_DEBUG_MODE": "true",
            "OKX_TIMEOUT_SECONDS": "60",
            "MARKET_META_CACHE_TTL_HOURS": "2",
            "MARKET_META_LOG_LEVEL": "DEBUG",
        },
    )
    def test_load_from_env(self):
        """Тест загрузки из переменных окружения"""
        config = MarketMetaConfig()

        assert config.environment == "production"
        assert config.debug_mode is True
        assert config.okx.timeout_seconds == 60
        assert config.cache.metadata_ttl_hours == 2
        assert config.logging.log_level == "DEBUG"

    @patch.dict(os.environ, {"MARKET_META_ENVIRONMENT": "invalid"})
    def test_from_env_validation_error(self):
        """Тест ошибки валидации при загрузке из env"""
        with pytest.raises(ConfigurationError) as exc_info:
            MarketMetaConfig.from_env()

        assert "Ошибки в конфигурации" in str(exc_info.value)
        assert "validation_errors" in exc_info.value.context


class TestConfigFunctions:
    """Тесты функций конфигурации"""

    def test_get_config_singleton(self):
        """Тест синглтона конфигурации"""
        # Сбрасываем глобальную конфигурацию
        import src.market_meta_backup.infrastructure.config as config_module

        config_module._config = None

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_set_config(self):
        """Тест установки конфигурации"""
        config = MarketMetaConfig()
        config.environment = "test"

        set_config(config)
        loaded_config = get_config()

        assert loaded_config is config
        assert loaded_config.environment == "test"

    @patch.dict(os.environ, {"MARKET_META_ENVIRONMENT": "staging"})
    def test_reload_config(self):
        """Тест перезагрузки конфигурации"""
        # Сбрасываем глобальную конфигурацию
        import src.market_meta_backup.infrastructure.config as config_module

        config_module._config = None

        config = reload_config()
        assert config.environment == "staging"

        # Проверяем, что глобальная конфигурация обновилась
        global_config = get_config()
        assert global_config.environment == "staging"


class TestConfigIntegration:
    """Интеграционные тесты конфигурации"""

    @patch.dict(
        os.environ,
        {
            "MARKET_META_ENVIRONMENT": "production",
            "MARKET_META_DEBUG_MODE": "false",
            "OKX_API_KEY": "test_key",
            "OKX_SECRET_KEY": "test_secret",
            "OKX_PASSPHRASE": "test_pass",
            "OKX_BASE_URL": "https://test.okx.com",
            "OKX_TIMEOUT_SECONDS": "45",
            "OKX_MAX_REQUESTS_PER_SECOND": "15",
            "OKX_MAX_RETRIES": "5",
            "MARKET_META_CACHE_TTL_HOURS": "3",
            "MARKET_META_AUTO_REFRESH_ENABLED": "false",
            "MARKET_META_LOG_LEVEL": "WARNING",
            "MARKET_META_LOG_FORMAT": "text",
            "MARKET_META_STRICT_VALIDATION": "false",
            "MARKET_META_MAX_POSITION_SIZE_USD": "20000",
            "MARKET_META_RISK_TOLERANCE": "aggressive",
            "MARKET_META_METRICS_ENABLED": "false",
        },
    )
    def test_full_config_from_env(self):
        """Тест полной загрузки конфигурации из переменных окружения"""
        config = MarketMetaConfig.from_env()

        # Проверяем общие настройки
        assert config.environment == "production"
        assert config.debug_mode is False

        # Проверяем OKX конфигурацию
        assert config.okx.api_key == "test_key"
        assert config.okx.secret_key == "test_secret"
        assert config.okx.passphrase == "test_pass"
        assert config.okx.base_url == "https://test.okx.com"
        assert config.okx.timeout_seconds == 45
        assert config.okx.max_requests_per_second == 15
        assert config.okx.max_retries == 5

        # Проверяем кэш конфигурацию
        assert config.cache.metadata_ttl_hours == 3
        assert config.cache.auto_refresh_enabled is False

        # Проверяем логирование
        assert config.logging.log_level == "WARNING"
        assert config.logging.log_format == "text"

        # Проверяем валидацию
        assert config.validation.strict_mode is False

        # Проверяем риски
        assert config.risk.max_position_size_usd == 20000.0
        assert config.risk.risk_tolerance == "aggressive"

        # Проверяем метрики
        assert config.metrics.enabled is False

        # Проверяем валидацию
        errors = config.validate()
        assert len(errors) == 0

    def test_boolean_parsing(self):
        """Тест парсинга boolean значений"""
        test_cases = [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ]

        for value, expected in test_cases:
            with patch.dict(os.environ, {"MARKET_META_DEBUG_MODE": value}):
                config = MarketMetaConfig()
                assert config.debug_mode is expected


if __name__ == "__main__":
    pytest.main([__file__])
