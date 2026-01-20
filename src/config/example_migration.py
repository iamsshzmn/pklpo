"""
Пример миграции старого кода на централизованную конфигурацию.

Этот файл показывает, как обновить существующий код для использования
нового централизованного подхода через Pydantic Settings.
"""

# =============================================================================
# БЫЛО (старый подход в features/config.py)
# =============================================================================

# import os
# from dataclasses import dataclass
#
# @dataclass
# class StreamingConfig:
#     CHUNKSIZE: int = 200_000
#     MAX_LOOKBACK: int = 200
#     BATCH_SIZE: int = 50_000
#
# def load_config_from_env() -> dict:
#     config = {}
#     config["CHUNKSIZE"] = int(os.getenv("FEATURES_CHUNKSIZE", "200000"))
#     config["BATCH_SIZE"] = int(os.getenv("FEATURES_BATCH_SIZE", "50000"))
#     return config
#
# # Использование:
# config = StreamingConfig()
# chunk_size = config.CHUNKSIZE

# =============================================================================
# СТАЛО (новый подход)
# =============================================================================

from src.config import get_settings

# Использование:
settings = get_settings()
chunk_size = settings.features.chunk_size
batch_size = settings.features.batch_size

# =============================================================================
# Примеры использования в разных модулях
# =============================================================================


def example_database_usage():
    """Пример использования настроек базы данных."""
    settings = get_settings()

    # Получение URL для подключения
    async_url = settings.db.async_url
    sync_url = settings.db.sync_url

    # Параметры пула соединений
    pool_size = settings.db.pool_size
    pool_timeout = settings.db.pool_timeout

    print(f"Database: {settings.db.name}@{settings.db.host}:{settings.db.port}")
    print(f"Pool: size={pool_size}, timeout={pool_timeout}")


def example_okx_usage():
    """Пример использования настроек OKX API."""
    settings = get_settings()

    # Проверка наличия credentials
    if not settings.okx.has_credentials:
        print("OKX API ключи не настроены!")
        return

    # Безопасное получение секретов
    api_key = settings.okx.api_key.get_secret_value()
    api_secret = settings.okx.api_secret.get_secret_value()

    # Rate limiting параметры
    max_rps = settings.okx.max_requests_per_second
    max_retries = settings.okx.max_retries

    print(f"OKX: max_rps={max_rps}, retries={max_retries}")


def example_risk_usage():
    """Пример использования настроек риска."""
    settings = get_settings()

    # Лимиты позиций
    max_leverage = settings.risk.max_leverage
    max_position = settings.risk.max_position_size_usd
    risk_per_trade = settings.risk.default_risk_per_trade

    # Лимиты убытков
    daily_limit = settings.risk.daily_loss_limit
    weekly_limit = settings.risk.weekly_loss_limit

    # Kill switch
    if settings.risk.enable_killswitch:
        auto_trigger = settings.risk.killswitch_auto_activate_on_loss
        print(f"Kill switch активируется при убытке > {auto_trigger:.0%}")

    print(f"Risk: leverage={max_leverage}x, position=${max_position:,.0f}")
    print(f"Limits: daily={daily_limit:.0%}, weekly={weekly_limit:.0%}")


def example_features_usage():
    """Пример использования настроек расчёта индикаторов."""
    settings = get_settings()

    # Chunking параметры
    chunk_size = settings.features.chunk_size
    batch_size = settings.features.batch_size
    workers = settings.features.parallel_workers

    # Quality параметры
    min_fill_rate = settings.features.min_fill_rate
    validate = settings.features.validate_results

    print(f"Features: chunks={chunk_size:,}, batch={batch_size:,}")
    print(f"Quality: fill_rate>={min_fill_rate:.0%}, validate={validate}")


def example_environment_check():
    """Пример проверки окружения."""
    settings = get_settings()

    if settings.is_production:
        print("⚠️  Production mode - будьте осторожны!")
        # Включаем строгие проверки
        assert settings.risk.enable_killswitch, "Kill switch обязателен в production"
    elif settings.is_development:
        print("🔧 Development mode")
        if settings.debug:
            print("   Debug mode enabled")


def example_custom_settings():
    """Пример с переопределением настроек для тестов."""
    from src.config.settings import Settings, DatabaseSettings, RiskSettings

    # Создаём кастомные настройки для тестов
    test_settings = Settings(
        environment="development",
        debug=True,
        db=DatabaseSettings(
            host="localhost",
            port=5433,  # Другой порт для тестов
            name="pklpo_test",
        ),
        risk=RiskSettings(
            max_leverage=5,  # Меньше leverage для тестов
            max_position_size_usd=1000.0,
        ),
    )

    print(f"Test DB: {test_settings.db.async_url}")
    print(f"Test leverage: {test_settings.risk.max_leverage}x")


if __name__ == "__main__":
    print("=" * 60)
    print("Примеры использования централизованной конфигурации")
    print("=" * 60)

    print("\n--- Database ---")
    example_database_usage()

    print("\n--- OKX API ---")
    example_okx_usage()

    print("\n--- Risk ---")
    example_risk_usage()

    print("\n--- Features ---")
    example_features_usage()

    print("\n--- Environment ---")
    example_environment_check()

    print("\n--- Custom Settings ---")
    example_custom_settings()
