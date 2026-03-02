"""
Domain layer - чистые модели, value objects, бизнес-правила, интерфейсы.
"""

from .contract import (
    ContractLoader,
    get_contract_loader,
    get_contract_version,
    get_params_hash,
)
from .exceptions import (
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
from .metadata import (
    FundingRate,
    InstrumentMetadata,
    InstrumentType,
    LiquidityParams,
    LotSize,
    MarginMode,
    MarketMetadata,
    TickSize,
)
from .quality import (
    COVERAGE_THRESHOLDS,
    DUPLICATE_RATE_THRESHOLDS,
    FRESHNESS_THRESHOLDS,
    FUNDING_EVENT_LAG_THRESHOLDS,
    FUNDING_FILL_THRESHOLDS,
    L2_EVENT_LAG_THRESHOLDS,
    L2_FILL_THRESHOLDS,
    OI_EVENT_LAG_THRESHOLDS,
    OI_FILL_THRESHOLDS,
    SMOKE_THRESHOLDS,
    CheckResult,
    QualityReport,
    Severity,
    Thresholds,
)
from .risk_limits import PositionLimit, PositionLimits, RiskLevel, RiskLimits
from .validators import MarketValidator, PositionValidator, ValidationResult

__all__ = [
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
    # Качество данных
    "Severity",
    "Thresholds",
    "CheckResult",
    "QualityReport",
    "FRESHNESS_THRESHOLDS",
    "COVERAGE_THRESHOLDS",
    "DUPLICATE_RATE_THRESHOLDS",
    "SMOKE_THRESHOLDS",
    "FUNDING_FILL_THRESHOLDS",
    "OI_FILL_THRESHOLDS",
    "L2_FILL_THRESHOLDS",
    "FUNDING_EVENT_LAG_THRESHOLDS",
    "OI_EVENT_LAG_THRESHOLDS",
    "L2_EVENT_LAG_THRESHOLDS",
    # Контракт
    "ContractLoader",
    "get_contract_loader",
    "get_contract_version",
    "get_params_hash",
]
