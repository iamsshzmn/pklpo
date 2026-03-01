"""
Централизованная конфигурация приложения.

Использование:
    from src.config import get_settings, Settings

    settings = get_settings()

    # Database
    db_url = settings.db.async_url

    # OKX
    if settings.okx.has_credentials:
        api_key = settings.okx.api_key.get_secret_value()

    # Risk limits
    max_leverage = settings.risk.max_leverage

    # Features
    batch_size = settings.features.batch_size

    # Environment check
    if settings.is_production:
        ...
"""

from .settings import (
    AirflowSettings,
    CacheSettings,
    DatabaseSettings,
    FeaturesSettings,
    LoggingSettings,
    ObservabilitySettings,
    OKXSettings,
    RiskSettings,
    Settings,
    get_database_url,
    get_okx_credentials,
    get_settings,
    reload_settings,
)

__all__ = [
    # Main
    "Settings",
    "get_settings",
    "reload_settings",
    # Sub-settings
    "DatabaseSettings",
    "OKXSettings",
    "FeaturesSettings",
    "RiskSettings",
    "CacheSettings",
    "LoggingSettings",
    "AirflowSettings",
    "ObservabilitySettings",
    # Legacy helpers
    "get_database_url",
    "get_okx_credentials",
]
