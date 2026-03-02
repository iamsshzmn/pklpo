"""
Централизованная конфигурация через Pydantic Settings.

Единая точка входа для всех настроек приложения.
Поддержка: .env файлы, переменные окружения, валидация, типизация.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Настройки подключения к базе данных."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 5432
    user: str = Field(alias="POSTGRES_USER", default="pklpo_user")
    password: SecretStr = Field(alias="POSTGRES_PASSWORD", default=SecretStr(""))
    name: str = Field(alias="POSTGRES_DB", default="pklpo")

    # Connection pool
    pool_size: int = 10
    pool_max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800

    @property
    def async_url(self) -> str:
        """Async connection URL для asyncpg."""
        pwd = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pwd}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        """Sync connection URL для psycopg2."""
        pwd = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pwd}@{self.host}:{self.port}/{self.name}"


class OKXSettings(BaseSettings):
    """Настройки OKX API."""

    model_config = SettingsConfigDict(
        env_prefix="OKX_",
        extra="ignore",
    )

    api_key: SecretStr = Field(default=SecretStr(""))
    api_secret: SecretStr = Field(default=SecretStr(""))
    passphrase: SecretStr = Field(default=SecretStr(""))
    base_url: str = "https://www.okx.com"

    # Rate limiting
    max_requests_per_second: int = 10
    max_requests_per_minute: int = 600

    # Retry
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    timeout: int = 30

    @property
    def has_credentials(self) -> bool:
        """Проверка наличия API ключей."""
        return bool(self.api_key.get_secret_value())


class FeaturesSettings(BaseSettings):
    """Настройки расчёта индикаторов."""

    model_config = SettingsConfigDict(
        env_prefix="FEATURES_",
        extra="ignore",
    )

    # Chunking
    chunk_size: int = 200_000
    max_lookback: int = 200
    overlap_size: int = 200

    # Database operations
    batch_size: int = 50_000
    insert_chunk_size: int = 50_000

    # Quality
    min_fill_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    validate_results: bool = True

    # Normalization
    volatility_normalize: bool = True
    normalize_window: int = 20

    # Performance
    parallel_workers: int = 4
    batch_timeout: int = 300

    # Memory management
    force_gc_after_chunk: bool = True
    clear_intermediate_objects: bool = True

    # Retry settings (for DB operations)
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0

    # Database persistence
    use_copy_from: bool = True
    temp_table_prefix: str = "temp_indicators_"

    # Logging
    log_memory: bool = True
    verbose: bool = False

    # TA backend selection (Phase 2 follow-up)
    ta_backend: Literal["auto", "pandas_ta", "talib", "fallback"] = "auto"

    # =========================================================================
    # OCP Configuration (Phase 2.2): Configurable indicators and thresholds
    # =========================================================================

    # Critical indicators that must always be calculated
    # These are added to the available set even if not explicitly requested
    critical_indicators: list[str] = Field(
        default=["t3_20", "rma_20", "ics_26"],
        description="Indicators that must always be calculated",
    )

    # Validation thresholds (OCP: modify without changing code)
    price_outlier_threshold: float = Field(
        default=0.02, ge=0.0, le=1.0,
        description="Maximum fraction of price outliers (2%)",
    )
    volume_outlier_threshold: float = Field(
        default=0.02, ge=0.0, le=1.0,
        description="Maximum fraction of volume outliers (2%)",
    )
    outlier_multiplier: float = Field(
        default=1.5, ge=1.0, le=5.0,
        description="IQR multiplier for outlier detection",
    )

    # Warm-up window settings
    ma_warmup_multiplier: float = Field(
        default=2.0, ge=1.0, le=5.0,
        description="Warm-up = MA period * multiplier",
    )
    atr_warmup_multiplier: float = Field(
        default=2.0, ge=1.0, le=5.0,
        description="Warm-up = ATR period * multiplier",
    )
    min_warmup_rows: int = Field(
        default=50, ge=10, le=500,
        description="Minimum warm-up rows",
    )

    # Price change validation
    min_price_change: float = Field(
        default=0.001, ge=0.0, le=0.1,
        description="Minimum price change (0.1%)",
    )
    max_price_change: float = Field(
        default=0.5, ge=0.1, le=1.0,
        description="Maximum price change (50%)",
    )

    # Group calculation configuration
    calculation_order: list[str] = Field(
        default=[
            "overlap", "ma", "oscillators", "volatility", "volume",
            "trend", "candles", "squeeze", "statistics", "performance",
        ],
        description="Order of group calculation",
    )

    # Feature periods for warm-up validation
    feature_periods: dict[str, int] = Field(
        default={
            "sma_20": 20, "sma_50": 50, "sma_200": 200,
            "ema_8": 8, "ema_21": 21, "ema_50": 50,
            "atr_14": 14, "atr_21": 21,
        },
        description="Feature name to period mapping for warm-up validation",
    )

    @field_validator("overlap_size")
    @classmethod
    def overlap_gte_lookback(cls, v: int, info) -> int:
        """Overlap должен быть >= max_lookback."""
        max_lookback: int = info.data.get("max_lookback", 200)
        return max(v, max_lookback)


class RiskSettings(BaseSettings):
    """Настройки риск-менеджмента."""

    model_config = SettingsConfigDict(
        env_prefix="RISK_",
        extra="ignore",
    )

    # Position limits
    default_risk_per_trade: float = Field(default=0.02, ge=0.001, le=0.1)
    max_risk_per_trade: float = Field(default=0.05, ge=0.01, le=0.2)
    max_position_size_usd: float = Field(default=10_000.0, gt=0)
    max_total_exposure_usd: float = Field(default=50_000.0, gt=0)
    max_leverage: int = Field(default=20, ge=1, le=125)
    max_concurrent_positions: int = Field(default=10, ge=1)

    # Loss limits
    daily_loss_limit: float = Field(default=0.10, ge=0.01, le=0.5)
    weekly_loss_limit: float = Field(default=0.20, ge=0.05, le=0.5)

    # Cooldowns
    cooldown_after_loss_sec: int = 3600
    cooldown_between_trades_sec: int = 300

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout_sec: int = 1800

    # Kill switch
    enable_killswitch: bool = True
    killswitch_auto_activate_on_loss: float = Field(default=0.15, ge=0.05, le=0.5)

    # Data quality
    min_data_quality_score: float = Field(default=0.8, ge=0.5, le=1.0)
    max_data_age_sec: int = 300

    @model_validator(mode="after")
    def validate_limits(self) -> "RiskSettings":
        """Валидация согласованности лимитов."""
        if self.default_risk_per_trade > self.max_risk_per_trade:
            raise ValueError(
                "default_risk_per_trade не может превышать max_risk_per_trade"
            )
        if self.daily_loss_limit > self.weekly_loss_limit:
            raise ValueError("daily_loss_limit не может превышать weekly_loss_limit")
        return self


class RetrySettings(BaseSettings):
    """
    Унифицированные настройки retry для всех внешних вызовов.

    Используется для:
    - Database operations
    - OKX API calls
    - External HTTP requests
    """

    model_config = SettingsConfigDict(
        env_prefix="RETRY_",
        extra="ignore",
    )

    # General retry settings
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay: float = Field(default=1.0, ge=0.1, le=30.0)
    max_delay: float = Field(default=60.0, ge=1.0, le=300.0)
    exponential_base: float = Field(default=2.0, ge=1.5, le=4.0)
    jitter: bool = Field(
        default=True, description="Add randomness to prevent thundering herd"
    )

    # Database-specific overrides
    db_max_attempts: int = Field(default=3, ge=1, le=10)
    db_base_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    db_max_delay: float = Field(default=10.0, ge=1.0, le=60.0)

    # API-specific overrides (longer timeouts for rate limiting)
    api_max_attempts: int = Field(default=5, ge=1, le=15)
    api_base_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    api_max_delay: float = Field(default=30.0, ge=1.0, le=120.0)


class CacheSettings(BaseSettings):
    """Настройки кэширования."""

    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        extra="ignore",
    )

    metadata_ttl_hours: int = 1
    instrument_ttl_hours: int = 1
    validation_ttl_minutes: int = 5

    auto_refresh_enabled: bool = True
    auto_refresh_interval_hours: int = 1

    max_size_mb: int = 100


class LoggingSettings(BaseSettings):
    """Настройки логирования."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        extra="ignore",
    )

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "text"] = "json"
    file: str | None = None

    max_size_mb: int = 10
    backup_count: int = 5

    mask_secrets: bool = True


class AirflowSettings(BaseSettings):
    """Настройки Airflow."""

    model_config = SettingsConfigDict(
        env_prefix="AIRFLOW_",
        extra="ignore",
    )

    db_user: str = "airflow"
    db_password: SecretStr = SecretStr("")
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "airflow"

    admin_password: SecretStr = SecretStr("")
    fernet_key: SecretStr = SecretStr("")
    secret_key: SecretStr = SecretStr("")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class ObservabilitySettings(BaseModel):
    """Observability settings (Prometheus/Pushgateway)."""

    prometheus_enabled: bool = Field(
        default_factory=lambda: _env_bool("OBSERVABILITY_PROMETHEUS_ENABLED", False)
    )
    prometheus_pushgateway_url: str = Field(
        default_factory=lambda: os.getenv("OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "")
    )
    metrics_prefix: str = Field(
        default_factory=lambda: os.getenv("OBSERVABILITY_METRICS_PREFIX", "pklpo")
    )
    job_name: str = Field(
        default_factory=lambda: os.getenv("OBSERVABILITY_JOB_NAME", "features_pipeline")
    )


class QuantSettings(BaseSettings):
    """
    Настройки Quant Stack (Phase 3).

    Env prefix: QUANT_
    Пример: QUANT_BARS_MODE=dollar QUANT_DOLLAR_BAR_VALUE=200000
    """

    model_config = SettingsConfigDict(
        env_prefix="QUANT_",
        extra="ignore",
    )

    # Bars
    bars_mode: Literal["time", "dollar"] = "time"
    dollar_bar_value: float = Field(default=200_000.0, gt=0)
    dollar_bar_min_trades: int = Field(default=1, ge=1)

    # Triple Barrier
    triple_pt: float = Field(default=0.02, gt=0, le=0.5)
    triple_sl: float = Field(default=0.01, gt=0, le=0.5)
    triple_max_h: int = Field(default=48, ge=1, le=500)

    # Validation
    purged_kfold_splits: int = Field(default=5, ge=2, le=20)
    embargo_pct: float = Field(default=0.01, ge=0.0, le=0.1)
    cpcv_n_groups: int = Field(default=6, ge=3, le=12)
    cpcv_n_test_groups: int = Field(default=2, ge=1)
    cpcv_max_paths: int = Field(default=50, ge=10, le=200)

    # Feature Selection
    feature_selection_method: Literal["mda", "mutual_info", "pca_variance"] = "mda"
    feature_selection_n_features: int = Field(default=50, ge=10, le=200)

    # Metalabeling
    metalabel_model: Literal["rf", "xgboost"] = "rf"
    metalabel_calibrate: bool = True
    metalabel_n_estimators: int = Field(default=500, ge=50, le=5000)

    # Metrics
    sharpe_periods: int = Field(
        default=365,
        ge=1,
        description="Количество периодов в году для аннуализации Sharpe. "
        "365 — крипто (дни), 252 — акции, 525600 — 1m бары.",
    )
    dsr_significance: float = Field(default=0.05, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_cpcv(self) -> "QuantSettings":
        """CPCV: n_test_groups должен быть меньше n_groups."""
        if self.cpcv_n_test_groups >= self.cpcv_n_groups:
            raise ValueError(
                f"cpcv_n_test_groups ({self.cpcv_n_test_groups}) "
                f"должен быть < cpcv_n_groups ({self.cpcv_n_groups})"
            )
        return self


class Settings(BaseSettings):
    """
    Главный класс настроек приложения.

    Использование:
        from src.config.settings import get_settings

        settings = get_settings()
        print(settings.db.async_url)
        print(settings.okx.has_credentials)
        print(settings.risk.max_leverage)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Sub-settings
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    okx: OKXSettings = Field(default_factory=OKXSettings)
    features: FeaturesSettings = Field(default_factory=FeaturesSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    airflow: AirflowSettings = Field(default_factory=AirflowSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    quant: QuantSettings = Field(default_factory=QuantSettings)

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    data_dir: Path = Field(default=Path("./data"))

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Возвращает синглтон настроек с кэшированием.

    Пример:
        settings = get_settings()

        # Database
        async_url = settings.db.async_url

        # OKX API
        if settings.okx.has_credentials:
            api_key = settings.okx.api_key.get_secret_value()

        # Risk
        max_leverage = settings.risk.max_leverage

        # Features
        batch_size = settings.features.batch_size
    """
    return Settings()


def reload_settings() -> Settings:
    """Перезагрузка настроек (очищает кэш)."""
    get_settings.cache_clear()
    return get_settings()


# Для обратной совместимости
def get_database_url() -> str:
    """Legacy: возвращает async database URL."""
    return get_settings().db.async_url


def get_okx_credentials() -> tuple[str, str, str]:
    """Legacy: возвращает OKX credentials."""
    s = get_settings().okx
    return (
        s.api_key.get_secret_value(),
        s.api_secret.get_secret_value(),
        s.passphrase.get_secret_value(),
    )
