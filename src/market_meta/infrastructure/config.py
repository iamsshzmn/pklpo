"""
Конфигурация модуля market_meta.

Поддерживает загрузку настроек из переменных окружения с валидацией.
"""

import os
from dataclasses import dataclass, field
from typing import Any

from ..domain.exceptions import ConfigurationError


@dataclass
class OKXConfig:
    """Конфигурация OKX API"""

    # API ключи (опциональные для публичных эндпоинтов)
    api_key: str | None = field(default=None, metadata={"env": "OKX_API_KEY"})
    secret_key: str | None = field(default=None, metadata={"env": "OKX_SECRET_KEY"})
    passphrase: str | None = field(default=None, metadata={"env": "OKX_PASSPHRASE"})

    # Настройки API
    base_url: str = field(
        default="https://www.okx.com", metadata={"env": "OKX_BASE_URL"}
    )
    timeout_seconds: int = field(default=30, metadata={"env": "OKX_TIMEOUT_SECONDS"})

    # Rate limiting
    max_requests_per_second: int = field(
        default=10, metadata={"env": "OKX_MAX_REQUESTS_PER_SECOND"}
    )
    max_requests_per_minute: int = field(
        default=600, metadata={"env": "OKX_MAX_REQUESTS_PER_MINUTE"}
    )

    # Retry настройки
    max_retries: int = field(default=3, metadata={"env": "OKX_MAX_RETRIES"})
    base_delay_seconds: float = field(
        default=1.0, metadata={"env": "OKX_BASE_DELAY_SECONDS"}
    )
    max_delay_seconds: float = field(
        default=60.0, metadata={"env": "OKX_MAX_DELAY_SECONDS"}
    )

    def validate(self) -> list[str]:
        """Валидирует конфигурацию OKX"""
        errors = []

        if self.timeout_seconds <= 0:
            errors.append("OKX_TIMEOUT_SECONDS должен быть положительным")

        if self.max_requests_per_second <= 0:
            errors.append("OKX_MAX_REQUESTS_PER_SECOND должен быть положительным")

        if self.max_retries < 0:
            errors.append("OKX_MAX_RETRIES не может быть отрицательным")

        if self.base_delay_seconds <= 0:
            errors.append("OKX_BASE_DELAY_SECONDS должен быть положительным")

        return errors


@dataclass
class CacheConfig:
    """Конфигурация кэширования"""

    # TTL для разных типов данных
    metadata_ttl_hours: int = field(
        default=1, metadata={"env": "MARKET_META_CACHE_TTL_HOURS"}
    )
    instrument_ttl_hours: int = field(
        default=1, metadata={"env": "MARKET_META_INSTRUMENT_CACHE_TTL_HOURS"}
    )
    validation_ttl_minutes: int = field(
        default=5, metadata={"env": "MARKET_META_VALIDATION_CACHE_TTL_MINUTES"}
    )

    # Авто-refresh
    auto_refresh_enabled: bool = field(
        default=True, metadata={"env": "MARKET_META_AUTO_REFRESH_ENABLED"}
    )
    auto_refresh_interval_hours: int = field(
        default=1, metadata={"env": "MARKET_META_AUTO_REFRESH_INTERVAL_HOURS"}
    )

    # Размер кэша
    max_cache_size_mb: int = field(
        default=100, metadata={"env": "MARKET_META_MAX_CACHE_SIZE_MB"}
    )

    def validate(self) -> list[str]:
        """Валидирует конфигурацию кэша"""
        errors = []

        if self.metadata_ttl_hours <= 0:
            errors.append("MARKET_META_CACHE_TTL_HOURS должен быть положительным")

        if self.auto_refresh_interval_hours <= 0:
            errors.append(
                "MARKET_META_AUTO_REFRESH_INTERVAL_HOURS должен быть положительным"
            )

        if self.max_cache_size_mb <= 0:
            errors.append("MARKET_META_MAX_CACHE_SIZE_MB должен быть положительным")

        return errors


@dataclass
class LoggingConfig:
    """Конфигурация логирования"""

    # Уровни логирования
    log_level: str = field(default="INFO", metadata={"env": "MARKET_META_LOG_LEVEL"})
    okx_log_level: str = field(
        default="INFO", metadata={"env": "MARKET_META_OKX_LOG_LEVEL"}
    )
    validation_log_level: str = field(
        default="INFO", metadata={"env": "MARKET_META_VALIDATION_LOG_LEVEL"}
    )

    # Файлы логов
    log_file: str | None = field(default=None, metadata={"env": "MARKET_META_LOG_FILE"})
    max_log_size_mb: int = field(
        default=10, metadata={"env": "MARKET_META_MAX_LOG_SIZE_MB"}
    )
    backup_count: int = field(
        default=5, metadata={"env": "MARKET_META_LOG_BACKUP_COUNT"}
    )

    # Форматирование
    log_format: str = field(
        default="json", metadata={"env": "MARKET_META_LOG_FORMAT"}
    )  # json, text
    include_timestamp: bool = field(
        default=True, metadata={"env": "MARKET_META_LOG_INCLUDE_TIMESTAMP"}
    )

    # Санитизация
    mask_api_keys: bool = field(
        default=True, metadata={"env": "MARKET_META_MASK_API_KEYS"}
    )
    max_message_length: int = field(
        default=1000, metadata={"env": "MARKET_META_MAX_MESSAGE_LENGTH"}
    )

    def validate(self) -> list[str]:
        """Валидирует конфигурацию логирования"""
        errors = []

        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            errors.append(f"MARKET_META_LOG_LEVEL должен быть одним из: {valid_levels}")

        if self.max_log_size_mb <= 0:
            errors.append("MARKET_META_MAX_LOG_SIZE_MB должен быть положительным")

        if self.backup_count < 0:
            errors.append("MARKET_META_LOG_BACKUP_COUNT не может быть отрицательным")

        if self.log_format not in ["json", "text"]:
            errors.append("MARKET_META_LOG_FORMAT должен быть 'json' или 'text'")

        if self.max_message_length <= 0:
            errors.append("MARKET_META_MAX_MESSAGE_LENGTH должен быть положительным")

        return errors


@dataclass
class ValidationConfig:
    """Конфигурация валидации"""

    # Строгость валидации
    strict_mode: bool = field(
        default=True, metadata={"env": "MARKET_META_STRICT_VALIDATION"}
    )
    allow_warnings: bool = field(
        default=True, metadata={"env": "MARKET_META_ALLOW_WARNINGS"}
    )

    # Лимиты валидации
    max_validation_errors: int = field(
        default=10, metadata={"env": "MARKET_META_MAX_VALIDATION_ERRORS"}
    )
    max_validation_warnings: int = field(
        default=20, metadata={"env": "MARKET_META_MAX_VALIDATION_WARNINGS"}
    )

    # Проверки
    validate_price_precision: bool = field(
        default=True, metadata={"env": "MARKET_META_VALIDATE_PRICE_PRECISION"}
    )
    validate_quantity_precision: bool = field(
        default=True, metadata={"env": "MARKET_META_VALIDATE_QUANTITY_PRECISION"}
    )
    validate_risk_limits: bool = field(
        default=True, metadata={"env": "MARKET_META_VALIDATE_RISK_LIMITS"}
    )
    validate_liquidity: bool = field(
        default=False, metadata={"env": "MARKET_META_VALIDATE_LIQUIDITY"}
    )

    def validate(self) -> list[str]:
        """Валидирует конфигурацию валидации"""
        errors = []

        if self.max_validation_errors <= 0:
            errors.append("MARKET_META_MAX_VALIDATION_ERRORS должен быть положительным")

        if self.max_validation_warnings <= 0:
            errors.append(
                "MARKET_META_MAX_VALIDATION_WARNINGS должен быть положительным"
            )

        return errors


@dataclass
class RiskConfig:
    """Конфигурация риск-менеджмента"""

    # Лимиты позиций
    max_position_size_usd: float = field(
        default=10000.0, metadata={"env": "MARKET_META_MAX_POSITION_SIZE_USD"}
    )
    max_total_exposure_usd: float = field(
        default=50000.0, metadata={"env": "MARKET_META_MAX_TOTAL_EXPOSURE_USD"}
    )
    max_leverage: int = field(default=10, metadata={"env": "MARKET_META_MAX_LEVERAGE"})

    # Политики риска
    risk_tolerance: str = field(
        default="conservative", metadata={"env": "MARKET_META_RISK_TOLERANCE"}
    )  # conservative, moderate, aggressive
    enable_position_limits: bool = field(
        default=True, metadata={"env": "MARKET_META_ENABLE_POSITION_LIMITS"}
    )
    enable_exposure_limits: bool = field(
        default=True, metadata={"env": "MARKET_META_ENABLE_EXPOSURE_LIMITS"}
    )

    # Алерты
    risk_alert_threshold: float = field(
        default=0.8, metadata={"env": "MARKET_META_RISK_ALERT_THRESHOLD"}
    )  # 80% от лимита
    critical_risk_threshold: float = field(
        default=0.95, metadata={"env": "MARKET_META_CRITICAL_RISK_THRESHOLD"}
    )  # 95% от лимита

    def validate(self) -> list[str]:
        """Валидирует конфигурацию рисков"""
        errors = []

        if self.max_position_size_usd <= 0:
            errors.append("MARKET_META_MAX_POSITION_SIZE_USD должен быть положительным")

        if self.max_total_exposure_usd <= 0:
            errors.append(
                "MARKET_META_MAX_TOTAL_EXPOSURE_USD должен быть положительным"
            )

        if self.max_leverage <= 0:
            errors.append("MARKET_META_MAX_LEVERAGE должен быть положительным")

        if self.risk_tolerance not in ["conservative", "moderate", "aggressive"]:
            errors.append(
                "MARKET_META_RISK_TOLERANCE должен быть 'conservative', 'moderate' или 'aggressive'"
            )

        if not 0 < self.risk_alert_threshold < 1:
            errors.append("MARKET_META_RISK_ALERT_THRESHOLD должен быть между 0 и 1")

        if not 0 < self.critical_risk_threshold < 1:
            errors.append("MARKET_META_CRITICAL_RISK_THRESHOLD должен быть между 0 и 1")

        if self.risk_alert_threshold >= self.critical_risk_threshold:
            errors.append(
                "MARKET_META_RISK_ALERT_THRESHOLD должен быть меньше MARKET_META_CRITICAL_RISK_THRESHOLD"
            )

        return errors


@dataclass
class MetricsConfig:
    """Конфигурация метрик"""

    # Включение метрик
    enabled: bool = field(default=True, metadata={"env": "MARKET_META_METRICS_ENABLED"})

    # Экспорт метрик
    export_metrics: bool = field(
        default=False, metadata={"env": "MARKET_META_EXPORT_METRICS"}
    )
    metrics_port: int = field(
        default=9090, metadata={"env": "MARKET_META_METRICS_PORT"}
    )

    # Интервалы сбора
    cache_metrics_interval_seconds: int = field(
        default=60, metadata={"env": "MARKET_META_CACHE_METRICS_INTERVAL"}
    )
    validation_metrics_interval_seconds: int = field(
        default=30, metadata={"env": "MARKET_META_VALIDATION_METRICS_INTERVAL"}
    )
    api_metrics_interval_seconds: int = field(
        default=15, metadata={"env": "MARKET_META_API_METRICS_INTERVAL"}
    )

    # Хранение метрик
    metrics_retention_hours: int = field(
        default=24, metadata={"env": "MARKET_META_METRICS_RETENTION_HOURS"}
    )

    def validate(self) -> list[str]:
        """Валидирует конфигурацию метрик"""
        errors = []

        if self.metrics_port <= 0 or self.metrics_port > 65535:
            errors.append("MARKET_META_METRICS_PORT должен быть между 1 и 65535")

        if self.cache_metrics_interval_seconds <= 0:
            errors.append(
                "MARKET_META_CACHE_METRICS_INTERVAL должен быть положительным"
            )

        if self.metrics_retention_hours <= 0:
            errors.append(
                "MARKET_META_METRICS_RETENTION_HOURS должен быть положительным"
            )

        return errors


@dataclass
class MarketMetaConfig:
    """Основная конфигурация модуля market_meta"""

    # Подконфигурации
    okx: OKXConfig = field(default_factory=OKXConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    # Общие настройки
    environment: str = field(
        default="development", metadata={"env": "MARKET_META_ENVIRONMENT"}
    )
    debug_mode: bool = field(default=False, metadata={"env": "MARKET_META_DEBUG_MODE"})

    # Пути к файлам
    config_file: str | None = field(
        default=None, metadata={"env": "MARKET_META_CONFIG_FILE"}
    )
    data_dir: str = field(default="./data", metadata={"env": "MARKET_META_DATA_DIR"})

    def __post_init__(self):
        """Загружает значения из переменных окружения после инициализации"""
        self._load_from_env()

    def _load_from_env(self):
        """Загружает значения из переменных окружения"""
        # Загружаем для каждой подконфигурации
        self._load_subconfig_from_env(self.okx)
        self._load_subconfig_from_env(self.cache)
        self._load_subconfig_from_env(self.logging)
        self._load_subconfig_from_env(self.validation)
        self._load_subconfig_from_env(self.risk)
        self._load_subconfig_from_env(self.metrics)

        # Загружаем общие настройки
        self._load_field_from_env(self, "environment")
        self._load_field_from_env(self, "debug_mode")
        self._load_field_from_env(self, "config_file")
        self._load_field_from_env(self, "data_dir")

    def _load_subconfig_from_env(self, subconfig):
        """Загружает значения из переменных окружения для подконфигурации"""
        for field_name, _field_info in subconfig.__dataclass_fields__.items():
            self._load_field_from_env(subconfig, field_name)

    def _load_field_from_env(self, obj, field_name: str):
        """Загружает значение поля из переменной окружения"""
        field_info = obj.__dataclass_fields__[field_name]
        env_var = field_info.metadata.get("env")

        if env_var and env_var in os.environ:
            value = os.environ[env_var]
            field_type = field_info.type

            # Преобразуем тип
            if field_type == bool:
                # Поддерживаем различные форматы boolean
                if value.lower() in ["true", "1", "yes", "on"]:
                    setattr(obj, field_name, True)
                elif value.lower() in ["false", "0", "no", "off"]:
                    setattr(obj, field_name, False)
            elif field_type == int:
                setattr(obj, field_name, int(value))
            elif field_type == float:
                setattr(obj, field_name, float(value))
            else:
                setattr(obj, field_name, value)

    def validate(self) -> list[str]:
        """Валидирует всю конфигурацию"""
        errors = []

        # Валидируем подконфигурации
        errors.extend(self.okx.validate())
        errors.extend(self.cache.validate())
        errors.extend(self.logging.validate())
        errors.extend(self.validation.validate())
        errors.extend(self.risk.validate())
        errors.extend(self.metrics.validate())

        # Валидируем общие настройки
        if self.environment not in ["development", "staging", "production"]:
            errors.append(
                "MARKET_META_ENVIRONMENT должен быть 'development', 'staging' или 'production'"
            )

        # Проверяем существование директории данных
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir, exist_ok=True)
            except Exception as e:
                errors.append(
                    f"Не удалось создать директорию данных {self.data_dir}: {e}"
                )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Преобразует конфигурацию в словарь"""
        return {
            "environment": self.environment,
            "debug_mode": self.debug_mode,
            "config_file": self.config_file,
            "data_dir": self.data_dir,
            "okx": {
                "api_key": "***" if self.okx.api_key else None,
                "secret_key": "***" if self.okx.secret_key else None,
                "passphrase": "***" if self.okx.passphrase else None,
                "base_url": self.okx.base_url,
                "timeout_seconds": self.okx.timeout_seconds,
                "max_requests_per_second": self.okx.max_requests_per_second,
                "max_retries": self.okx.max_retries,
                "base_delay_seconds": self.okx.base_delay_seconds,
                "max_delay_seconds": self.okx.max_delay_seconds,
            },
            "cache": {
                "metadata_ttl_hours": self.cache.metadata_ttl_hours,
                "auto_refresh_enabled": self.cache.auto_refresh_enabled,
                "auto_refresh_interval_hours": self.cache.auto_refresh_interval_hours,
                "max_cache_size_mb": self.cache.max_cache_size_mb,
            },
            "logging": {
                "log_level": self.logging.log_level,
                "log_file": self.logging.log_file,
                "log_format": self.logging.log_format,
                "mask_api_keys": self.logging.mask_api_keys,
            },
            "validation": {
                "strict_mode": self.validation.strict_mode,
                "allow_warnings": self.validation.allow_warnings,
                "validate_risk_limits": self.validation.validate_risk_limits,
            },
            "risk": {
                "max_position_size_usd": self.risk.max_position_size_usd,
                "max_total_exposure_usd": self.risk.max_total_exposure_usd,
                "max_leverage": self.risk.max_leverage,
                "risk_tolerance": self.risk.risk_tolerance,
            },
            "metrics": {
                "enabled": self.metrics.enabled,
                "export_metrics": self.metrics.export_metrics,
                "metrics_port": self.metrics.metrics_port,
            },
        }

    @classmethod
    def from_env(cls) -> "MarketMetaConfig":
        """Создает конфигурацию из переменных окружения"""
        config = cls()
        errors = config.validate()

        if errors:
            raise ConfigurationError(
                "Ошибки в конфигурации", context={"validation_errors": errors}
            )

        return config

    @classmethod
    def from_file(cls, config_file: str) -> "MarketMetaConfig":
        """Создает конфигурацию из файла (будущая реализация)"""
        # TODO: Реализовать загрузку из YAML/JSON файла
        raise NotImplementedError("Загрузка из файла пока не реализована")


# Глобальный экземпляр конфигурации
_config: MarketMetaConfig | None = None


def get_config() -> MarketMetaConfig:
    """Возвращает глобальную конфигурацию"""
    global _config
    if _config is None:
        _config = MarketMetaConfig.from_env()
    return _config


def set_config(config: MarketMetaConfig):
    """Устанавливает глобальную конфигурацию"""
    global _config
    _config = config


def reload_config():
    """Перезагружает конфигурацию из переменных окружения"""
    global _config
    _config = MarketMetaConfig.from_env()
    return _config
