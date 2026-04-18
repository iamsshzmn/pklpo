"""
Configuration for the market_meta module.

Supports loading settings from environment variables with validation.
"""

import os
from dataclasses import dataclass, field
from typing import Any

from ..domain.exceptions import ConfigurationError


@dataclass
class OKXConfig:
    """OKX API configuration"""

    # API keys (optional for public endpoints)
    api_key: str | None = field(default=None, metadata={"env": "OKX_API_KEY"})
    secret_key: str | None = field(default=None, metadata={"env": "OKX_SECRET_KEY"})
    passphrase: str | None = field(default=None, metadata={"env": "OKX_PASSPHRASE"})

    # API settings
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

    # Retry settings
    max_retries: int = field(default=3, metadata={"env": "OKX_MAX_RETRIES"})
    base_delay_seconds: float = field(
        default=1.0, metadata={"env": "OKX_BASE_DELAY_SECONDS"}
    )
    max_delay_seconds: float = field(
        default=60.0, metadata={"env": "OKX_MAX_DELAY_SECONDS"}
    )

    def validate(self) -> list[str]:
        """Validates OKX configuration"""
        errors = []

        if self.timeout_seconds <= 0:
            errors.append("OKX_TIMEOUT_SECONDS must be positive")

        if self.max_requests_per_second <= 0:
            errors.append("OKX_MAX_REQUESTS_PER_SECOND must be positive")

        if self.max_retries < 0:
            errors.append("OKX_MAX_RETRIES cannot be negative")

        if self.base_delay_seconds <= 0:
            errors.append("OKX_BASE_DELAY_SECONDS must be positive")

        return errors


@dataclass
class CacheConfig:
    """Cache configuration"""

    # TTL for different data types
    metadata_ttl_hours: int = field(
        default=1, metadata={"env": "MARKET_META_CACHE_TTL_HOURS"}
    )
    instrument_ttl_hours: int = field(
        default=1, metadata={"env": "MARKET_META_INSTRUMENT_CACHE_TTL_HOURS"}
    )
    validation_ttl_minutes: int = field(
        default=5, metadata={"env": "MARKET_META_VALIDATION_CACHE_TTL_MINUTES"}
    )

    # Auto-refresh
    auto_refresh_enabled: bool = field(
        default=True, metadata={"env": "MARKET_META_AUTO_REFRESH_ENABLED"}
    )
    auto_refresh_interval_hours: int = field(
        default=1, metadata={"env": "MARKET_META_AUTO_REFRESH_INTERVAL_HOURS"}
    )

    # Cache size
    max_cache_size_mb: int = field(
        default=100, metadata={"env": "MARKET_META_MAX_CACHE_SIZE_MB"}
    )

    def validate(self) -> list[str]:
        """Validates cache configuration"""
        errors = []

        if self.metadata_ttl_hours <= 0:
            errors.append("MARKET_META_CACHE_TTL_HOURS must be positive")

        if self.auto_refresh_interval_hours <= 0:
            errors.append(
                "MARKET_META_AUTO_REFRESH_INTERVAL_HOURS must be positive"
            )

        if self.max_cache_size_mb <= 0:
            errors.append("MARKET_META_MAX_CACHE_SIZE_MB must be positive")

        return errors


@dataclass
class LoggingConfig:
    """Logging configuration"""

    # Log levels
    log_level: str = field(default="INFO", metadata={"env": "MARKET_META_LOG_LEVEL"})
    okx_log_level: str = field(
        default="INFO", metadata={"env": "MARKET_META_OKX_LOG_LEVEL"}
    )
    validation_log_level: str = field(
        default="INFO", metadata={"env": "MARKET_META_VALIDATION_LOG_LEVEL"}
    )

    # Log files
    log_file: str | None = field(default=None, metadata={"env": "MARKET_META_LOG_FILE"})
    max_log_size_mb: int = field(
        default=10, metadata={"env": "MARKET_META_MAX_LOG_SIZE_MB"}
    )
    backup_count: int = field(
        default=5, metadata={"env": "MARKET_META_LOG_BACKUP_COUNT"}
    )

    # Formatting
    log_format: str = field(
        default="json", metadata={"env": "MARKET_META_LOG_FORMAT"}
    )  # json, text
    include_timestamp: bool = field(
        default=True, metadata={"env": "MARKET_META_LOG_INCLUDE_TIMESTAMP"}
    )

    # Sanitization
    mask_api_keys: bool = field(
        default=True, metadata={"env": "MARKET_META_MASK_API_KEYS"}
    )
    max_message_length: int = field(
        default=1000, metadata={"env": "MARKET_META_MAX_MESSAGE_LENGTH"}
    )

    def validate(self) -> list[str]:
        """Validates logging configuration"""
        errors = []

        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            errors.append(f"MARKET_META_LOG_LEVEL must be one of: {valid_levels}")

        if self.max_log_size_mb <= 0:
            errors.append("MARKET_META_MAX_LOG_SIZE_MB must be positive")

        if self.backup_count < 0:
            errors.append("MARKET_META_LOG_BACKUP_COUNT cannot be negative")

        if self.log_format not in ["json", "text"]:
            errors.append("MARKET_META_LOG_FORMAT must be 'json' or 'text'")

        if self.max_message_length <= 0:
            errors.append("MARKET_META_MAX_MESSAGE_LENGTH must be positive")

        return errors


@dataclass
class ValidationConfig:
    """Validation configuration"""

    # Validation strictness
    strict_mode: bool = field(
        default=True, metadata={"env": "MARKET_META_STRICT_VALIDATION"}
    )
    allow_warnings: bool = field(
        default=True, metadata={"env": "MARKET_META_ALLOW_WARNINGS"}
    )

    # Validation limits
    max_validation_errors: int = field(
        default=10, metadata={"env": "MARKET_META_MAX_VALIDATION_ERRORS"}
    )
    max_validation_warnings: int = field(
        default=20, metadata={"env": "MARKET_META_MAX_VALIDATION_WARNINGS"}
    )

    # Checks
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
        """Validates validation configuration"""
        errors = []

        if self.max_validation_errors <= 0:
            errors.append("MARKET_META_MAX_VALIDATION_ERRORS must be positive")

        if self.max_validation_warnings <= 0:
            errors.append(
                "MARKET_META_MAX_VALIDATION_WARNINGS must be positive"
            )

        return errors


@dataclass
class RiskConfig:
    """Risk management configuration"""

    # Position limits
    max_position_size_usd: float = field(
        default=10000.0, metadata={"env": "MARKET_META_MAX_POSITION_SIZE_USD"}
    )
    max_total_exposure_usd: float = field(
        default=50000.0, metadata={"env": "MARKET_META_MAX_TOTAL_EXPOSURE_USD"}
    )
    max_leverage: int = field(default=10, metadata={"env": "MARKET_META_MAX_LEVERAGE"})

    # Risk policies
    risk_tolerance: str = field(
        default="conservative", metadata={"env": "MARKET_META_RISK_TOLERANCE"}
    )  # conservative, moderate, aggressive
    enable_position_limits: bool = field(
        default=True, metadata={"env": "MARKET_META_ENABLE_POSITION_LIMITS"}
    )
    enable_exposure_limits: bool = field(
        default=True, metadata={"env": "MARKET_META_ENABLE_EXPOSURE_LIMITS"}
    )

    # Alerts
    risk_alert_threshold: float = field(
        default=0.8, metadata={"env": "MARKET_META_RISK_ALERT_THRESHOLD"}
    )  # 80% of limit
    critical_risk_threshold: float = field(
        default=0.95, metadata={"env": "MARKET_META_CRITICAL_RISK_THRESHOLD"}
    )  # 95% of limit

    def validate(self) -> list[str]:
        """Validates risk configuration"""
        errors = []

        if self.max_position_size_usd <= 0:
            errors.append("MARKET_META_MAX_POSITION_SIZE_USD must be positive")

        if self.max_total_exposure_usd <= 0:
            errors.append(
                "MARKET_META_MAX_TOTAL_EXPOSURE_USD must be positive"
            )

        if self.max_leverage <= 0:
            errors.append("MARKET_META_MAX_LEVERAGE must be positive")

        if self.risk_tolerance not in ["conservative", "moderate", "aggressive"]:
            errors.append(
                "MARKET_META_RISK_TOLERANCE must be 'conservative', 'moderate' or 'aggressive'"
            )

        if not 0 < self.risk_alert_threshold < 1:
            errors.append("MARKET_META_RISK_ALERT_THRESHOLD must be between 0 and 1")

        if not 0 < self.critical_risk_threshold < 1:
            errors.append("MARKET_META_CRITICAL_RISK_THRESHOLD must be between 0 and 1")

        if self.risk_alert_threshold >= self.critical_risk_threshold:
            errors.append(
                "MARKET_META_RISK_ALERT_THRESHOLD must be less than MARKET_META_CRITICAL_RISK_THRESHOLD"
            )

        return errors


@dataclass
class MetricsConfig:
    """Metrics configuration"""

    # Enable metrics
    enabled: bool = field(default=True, metadata={"env": "MARKET_META_METRICS_ENABLED"})

    # Metrics export
    export_metrics: bool = field(
        default=False, metadata={"env": "MARKET_META_EXPORT_METRICS"}
    )
    metrics_port: int = field(
        default=9090, metadata={"env": "MARKET_META_METRICS_PORT"}
    )

    # Collection intervals
    cache_metrics_interval_seconds: int = field(
        default=60, metadata={"env": "MARKET_META_CACHE_METRICS_INTERVAL"}
    )
    validation_metrics_interval_seconds: int = field(
        default=30, metadata={"env": "MARKET_META_VALIDATION_METRICS_INTERVAL"}
    )
    api_metrics_interval_seconds: int = field(
        default=15, metadata={"env": "MARKET_META_API_METRICS_INTERVAL"}
    )

    # Metrics retention
    metrics_retention_hours: int = field(
        default=24, metadata={"env": "MARKET_META_METRICS_RETENTION_HOURS"}
    )

    def validate(self) -> list[str]:
        """Validates metrics configuration"""
        errors = []

        if self.metrics_port <= 0 or self.metrics_port > 65535:
            errors.append("MARKET_META_METRICS_PORT must be between 1 and 65535")

        if self.cache_metrics_interval_seconds <= 0:
            errors.append(
                "MARKET_META_CACHE_METRICS_INTERVAL must be positive"
            )

        if self.metrics_retention_hours <= 0:
            errors.append(
                "MARKET_META_METRICS_RETENTION_HOURS must be positive"
            )

        return errors


@dataclass
class MarketMetaConfig:
    """Main configuration for the market_meta module"""

    # Sub-configurations
    okx: OKXConfig = field(default_factory=OKXConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    # General settings
    environment: str = field(
        default="development", metadata={"env": "MARKET_META_ENVIRONMENT"}
    )
    debug_mode: bool = field(default=False, metadata={"env": "MARKET_META_DEBUG_MODE"})

    # File paths
    config_file: str | None = field(
        default=None, metadata={"env": "MARKET_META_CONFIG_FILE"}
    )
    data_dir: str = field(default="./data", metadata={"env": "MARKET_META_DATA_DIR"})

    def __post_init__(self):
        """Loads values from environment variables after initialization"""
        self._load_from_env()

    def _load_from_env(self):
        """Loads values from environment variables"""
        # Load for each sub-configuration
        self._load_subconfig_from_env(self.okx)
        self._load_subconfig_from_env(self.cache)
        self._load_subconfig_from_env(self.logging)
        self._load_subconfig_from_env(self.validation)
        self._load_subconfig_from_env(self.risk)
        self._load_subconfig_from_env(self.metrics)

        # Load general settings
        self._load_field_from_env(self, "environment")
        self._load_field_from_env(self, "debug_mode")
        self._load_field_from_env(self, "config_file")
        self._load_field_from_env(self, "data_dir")

    def _load_subconfig_from_env(self, subconfig):
        """Loads values from environment variables for a sub-configuration"""
        for field_name, _field_info in subconfig.__dataclass_fields__.items():
            self._load_field_from_env(subconfig, field_name)

    def _load_field_from_env(self, obj, field_name: str):
        """Loads a field value from an environment variable"""
        field_info = obj.__dataclass_fields__[field_name]
        env_var = field_info.metadata.get("env")

        if env_var and env_var in os.environ:
            value = os.environ[env_var]
            field_type = field_info.type

            # Convert type
            if field_type is bool:
                # Support various boolean formats
                if value.lower() in ["true", "1", "yes", "on"]:
                    setattr(obj, field_name, True)
                elif value.lower() in ["false", "0", "no", "off"]:
                    setattr(obj, field_name, False)
            elif field_type is int:
                setattr(obj, field_name, int(value))
            elif field_type is float:
                setattr(obj, field_name, float(value))
            else:
                setattr(obj, field_name, value)

    def validate(self) -> list[str]:
        """Validates the entire configuration"""
        errors = []

        # Validate sub-configurations
        errors.extend(self.okx.validate())
        errors.extend(self.cache.validate())
        errors.extend(self.logging.validate())
        errors.extend(self.validation.validate())
        errors.extend(self.risk.validate())
        errors.extend(self.metrics.validate())

        # Validate general settings
        if self.environment not in ["development", "staging", "production"]:
            errors.append(
                "MARKET_META_ENVIRONMENT must be 'development', 'staging' or 'production'"
            )

        # Check data directory existence
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir, exist_ok=True)
            except Exception as e:
                errors.append(
                    f"Failed to create data directory {self.data_dir}: {e}"
                )

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Converts configuration to a dictionary"""
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
        """Creates configuration from environment variables"""
        config = cls()
        errors = config.validate()

        if errors:
            raise ConfigurationError(
                "Configuration errors", context={"validation_errors": errors}
            )

        return config

    @classmethod
    def from_file(cls, config_file: str) -> "MarketMetaConfig":
        """Creates configuration from a file (future implementation)"""
        # TODO: Implement loading from YAML/JSON file
        raise NotImplementedError("Loading from file is not yet implemented")


# Global configuration instance
_config: MarketMetaConfig | None = None


def get_config() -> MarketMetaConfig:
    """Returns the global configuration"""
    global _config
    if _config is None:
        _config = MarketMetaConfig.from_env()
    return _config


def set_config(config: MarketMetaConfig):
    """Sets the global configuration"""
    global _config
    _config = config


def reload_config():
    """Reloads configuration from environment variables"""
    global _config
    _config = MarketMetaConfig.from_env()
    return _config
