"""Domain-layer exports for the unified ``src.candles`` module."""

from .batch_policy import DynamicBatchPolicy
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
from .sync_config import DEFAULT_CONFIG, SWAP_BARS
from .timeframes import TF_TO_MS, TF_TO_SEC
from .validators import MarketValidator, PositionValidator, ValidationResult

__all__ = [name for name in globals() if not name.startswith("_")]
