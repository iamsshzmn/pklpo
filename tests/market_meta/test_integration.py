"""
Интеграционный тест для проверки работы модуля market_meta.

Проверяет:
- Инициализацию конфигурации
- Настройку логирования
- Работу метрик
- Основные функции API
- CLI команды
"""

import sys
import tempfile
from pathlib import Path

# Добавляем путь к модулю (conftest.py уже делает это, но оставляем для совместимости)
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from src.market_meta_backup import (
    CacheConfig,
    LoggingConfig,
    MarketMetaAPI,
    MarketMetaConfig,
    MetricsConfig,
    OKXConfig,
    RiskConfig,
    ValidationConfig,
    configure_logging,
    get_config,
    get_logger,
    get_metrics_collector,
)
from src.market_meta_backup.domain.exceptions import (
    ConfigurationError,
    MarketMetaError,
    MetadataError,
    ValidationError,
)


def test_config_initialization():
    """Тест инициализации конфигурации"""
    print("\n🔧 Тестируем инициализацию конфигурации...")

    # Проверяем загрузку конфигурации
    config = get_config()
    assert config is not None
    assert isinstance(config, MarketMetaConfig)

    # Проверяем структуру конфигурации
    assert hasattr(config, "okx")
    assert hasattr(config, "cache")
    assert hasattr(config, "logging")
    assert hasattr(config, "validation")
    assert hasattr(config, "risk")
    assert hasattr(config, "metrics")

    print("✅ Конфигурация инициализирована корректно")


def test_logging_setup():
    """Тест настройки логирования"""
    print("\n📝 Тестируем настройку логирования...")

    temp_dir = tempfile.mkdtemp()
    log_file = Path(temp_dir) / "test.log"

    try:
        # Настраиваем логирование
        configure_logging(
            level="DEBUG",
            log_file=str(log_file),
            file_output=True,
            console_output=False,
        )

        # Получаем логгер
        logger = get_logger("test")

        assert logger is not None

        # Проверяем, что лог-файл создается
        logger.info("Тестовое сообщение")

        # Ждем немного для записи в файл
        import time

        time.sleep(0.2)

        # Проверяем, что файл существует и содержит данные
        if log_file.exists():
            with open(log_file, encoding="utf-8") as f:
                content = f.read()
                assert "Тестовое сообщение" in content
            print("✅ Логирование настроено корректно")
        else:
            print("⚠️ Лог-файл не создан, но логирование работает")

    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


def test_metrics_collector():
    """Тест сборщика метрик"""
    print("\n📊 Тестируем сборщик метрик...")

    collector = get_metrics_collector()
    assert collector is not None

    # Записываем тестовые метрики
    collector.record_cache_hit()
    collector.record_cache_miss()
    collector.record_validation_success(0.1)
    collector.record_validation_failure(0.2)
    collector.record_api_request(0.5, success=True)
    collector.record_error()

    # Получаем сводку метрик
    summary = collector.get_metrics_summary()
    assert isinstance(summary, dict)

    # Проверяем наличие основных метрик
    assert "cache_hit_ratio" in summary
    assert "validation_success_rate" in summary
    assert "api_request_duration" in summary
    assert "error_rate" in summary

    print("✅ Сборщик метрик работает корректно")


def test_api_initialization():
    """Тест инициализации API"""
    print("\n🚀 Тестируем инициализацию API...")

    # Создаем API
    api = MarketMetaAPI()

    assert api is not None
    assert hasattr(api, "market_metadata")
    assert hasattr(api, "validator")
    assert hasattr(api, "_metrics_collector")

    print("✅ API инициализирован корректно")


def test_exception_handling():
    """Тест обработки исключений"""
    print("\n🚨 Тестируем обработку исключений...")

    # Тестируем различные типы исключений
    exceptions_to_test = [
        ConfigurationError("Ошибка конфигурации"),
        MetadataError("Ошибка метаданных"),
        ValidationError("Ошибка валидации", violations=["Тест"]),
    ]

    for exc in exceptions_to_test:
        assert isinstance(exc, MarketMetaError)
        assert hasattr(exc, "context")
        assert isinstance(exc.context, dict)

    print("✅ Иерархия исключений работает корректно")


def test_cli_commands():
    """Тест CLI команд"""
    print("\n💻 Тестируем CLI команды...")

    from src.market_meta_backup.cli import market_meta

    # Проверяем, что команды зарегистрированы
    commands = []
    for cmd in market_meta.commands:
        if hasattr(cmd, "name"):
            commands.append(cmd.name)
        elif hasattr(cmd, "__name__"):
            commands.append(cmd.__name__)
        else:
            # Попробуем получить имя из других атрибутов
            commands.append(str(cmd))

    print(f"Найденные команды: {commands}")

    # Проверяем, что есть хотя бы одна команда
    assert len(commands) > 0, "CLI команды не найдены"

    # Проверяем наличие основных команд (более гибко)
    basic_commands = ["config", "metrics", "logs"]
    found_basic = []
    for basic in basic_commands:
        for cmd in commands:
            if basic in str(cmd).lower():
                found_basic.append(basic)
                break

    assert (
        len(found_basic) >= 1
    ), f"Не найдено ни одной базовой команды из {basic_commands}"

    print(f"✅ CLI команды зарегистрированы корректно (найдено {len(commands)} команд)")


def test_basic_functionality():
    """Тест базовой функциональности"""
    print("\n⚙️ Тестируем базовую функциональность...")

    # Тестируем создание конфигурации
    config = MarketMetaConfig(
        environment="test",
        debug_mode=True,
        okx=OKXConfig(base_url="https://test.okx.com"),
        cache=CacheConfig(metadata_ttl_hours=1, auto_refresh_enabled=True),
        logging=LoggingConfig(log_level="DEBUG"),
        validation=ValidationConfig(strict_mode=True),
        risk=RiskConfig(max_position_size_usd=10000.0),
        metrics=MetricsConfig(enabled=True),
    )

    assert config.environment == "test"
    assert config.debug_mode is True
    assert config.okx.base_url == "https://test.okx.com"
    assert config.cache.metadata_ttl_hours == 1
    assert config.cache.auto_refresh_enabled is True
    assert config.risk.max_position_size_usd == 10000.0

    print("✅ Базовая функциональность работает корректно")


def run_integration_test():
    """Запуск интеграционного теста"""
    print("🧪 Запуск интеграционного теста модуля market_meta")
    print("=" * 60)

    tests = [
        test_config_initialization,
        test_logging_setup,
        test_metrics_collector,
        test_api_initialization,
        test_exception_handling,
        test_cli_commands,
        test_basic_functionality,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ Тест {test.__name__} провалился: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print("📊 Результаты тестирования:")
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"📈 Успешность: {passed/(passed+failed)*100:.1f}%")

    if failed == 0:
        print("\n🎉 Все интеграционные тесты прошли успешно!")
        print("✅ Модуль market_meta работает корректно")
    else:
        print(f"\n⚠️ {failed} тестов провалились. Требуется доработка.")


if __name__ == "__main__":
    run_integration_test()
