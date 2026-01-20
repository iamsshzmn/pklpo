"""
Централизованная конфигурация через Pydantic Settings.

Единая точка входа для всех настроек приложения.
Поддержка: .env файлы, переменные окружения, валидация, типизация.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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

    # Logging
    log_memory: bool = True
    verbose: bool = False

    @field_validator("overlap_size")
    @classmethod
    def overlap_gte_lookback(cls, v: int, info) -> int:
        """Overlap должен быть >= max_lookback."""
        max_lookback = info.data.get("max_lookback", 200)
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
    cache: CacheSettings = Field(default_factory=CacheSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    airflow: AirflowSettings = Field(default_factory=AirflowSettings)

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
