"""
Market Meta Module - Метаданные рынка, валидаторы и биржевые специфики.

Этот модуль содержит:
- Метаданные инструментов (размер тика, лот, номинальная стоимость)
- Валидаторы времени выполнения
- Уровни лимитов риска
- Поддержка режимов маржи
- Обработка ставок финансирования
- Фильтры ликвидности

Основной API:
- refresh_okx_meta() - обновление метаданных с OKX
- validate_order(symbol, price, qty) -> list[violations] - валидация ордеров
"""

# Legacy клиенты (для обратной совместимости)
# Основные функции API
from .application.api import (
    MarketMetaAPI,
    calculate_notional_value,
    get_funding_rate,
    get_instrument_info,
    get_liquidity_info,
    get_mark_price,
    get_open_interest,
    refresh_okx_meta,
    # Новые расширенные функции
    refresh_okx_meta_extended,
    validate_order,
)

# CLI команды
from .cli import market_meta

# Domain layer
from .domain.exceptions import (
    CacheError,
    ConfigurationError,
    MarketMetaError,
    MetadataError,
    MetadataStaleError,
    OKXIntegrationError,
    RiskError,
    ValidationError,
    is_retryable_error,
)
from .domain.metadata import (
    FundingRate,
    InstrumentMetadata,
    InstrumentType,
    LiquidityParams,
    LotSize,
    MarginMode,
    MarketMetadata,
    TickSize,
)
from .domain.risk_limits import PositionLimit, PositionLimits, RiskLevel, RiskLimits
from .domain.validators import MarketValidator, PositionValidator, ValidationResult

# Infrastructure layer
from .infrastructure import (
    LOGGER_NAME,
    MarketDataAggregator,
    MarketDataExt,
    MarketDataExtRepository,
    MarketDataExtRetention,
    MarketDataLoader,
    MarketDataNormalizer,
    MarketMetaConfig,
    MarketMetadataDB,
    MetricsCollector,
    MetricsExporter,
    MetricsMonitor,
    OHLCVAligner,
    OKXClient,
    OKXMarket,
    OKXMetadataLoader,
    OKXOrders,
    RiskLimitsDB,
    ValidationCache,
    ValidationLog,
    configure_logging,
    get_config,
    get_logger,
    get_metrics_collector,
    log_validation_result,
    measure_async_time,
    measure_time,
)
from .infrastructure.config import (
    CacheConfig,
    LoggingConfig,
    MetricsConfig,
    OKXConfig,
    RiskConfig,
    ValidationConfig,
)

__all__ = [
    # Основные функции API
    "refresh_okx_meta",
    "validate_order",
    "get_instrument_info",
    "calculate_notional_value",
    "MarketMetaAPI",
    # Новые расширенные функции
    "refresh_okx_meta_extended",
    "get_funding_rate",
    "get_mark_price",
    "get_liquidity_info",
    "get_open_interest",
    # Модели данных
    "InstrumentMetadata",
    "MarketMetadata",
    "TickSize",
    "LotSize",
    "FundingRate",
    "LiquidityParams",
    "MarginMode",
    "InstrumentType",
    # Валидаторы
    "MarketValidator",
    "PositionValidator",
    "ValidationResult",
    # Риск-менеджмент
    "RiskLimits",
    "PositionLimit",
    "PositionLimits",
    "RiskLevel",
    # Конфигурация
    "MarketMetaConfig",
    "CacheConfig",
    "LoggingConfig",
    "MetricsConfig",
    "OKXConfig",
    "RiskConfig",
    "ValidationConfig",
    "get_config",
    # Логирование
    "LOGGER_NAME",
    "get_logger",
    "configure_logging",
    "log_validation_result",
    # Метрики
    "get_metrics_collector",
    "measure_time",
    "measure_async_time",
    "MetricsCollector",
    "MetricsExporter",
    "MetricsMonitor",
    # Исключения
    "MarketMetaError",
    "MetadataError",
    "MetadataStaleError",
    "ValidationError",
    "RiskError",
    "OKXIntegrationError",
    "ConfigurationError",
    "CacheError",
    "is_retryable_error",
    # CLI команды
    "market_meta",
    # OKX интеграция
    "OKXMetadataLoader",
    # Загрузчик расширенных данных
    "MarketDataLoader",
    "OHLCVAligner",
    "MarketDataNormalizer",
    "MarketDataAggregator",
    # База данных
    "MarketDataExt",
    "MarketDataExtRepository",
    "MarketDataExtRetention",
    "MarketMetadataDB",
    "ValidationCache",
    "RiskLimitsDB",
    "ValidationLog",
]

# Версия модуля
__version__ = "1.0.0"

# Автор
__author__ = "PKLPO Team"

# Описание
__description__ = "Модуль метаданных рынка, валидаторов и биржевых специфик для торговой системы PKLPO"
