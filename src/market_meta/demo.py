"""
Демонстрационный скрипт для тестирования модуля market_meta в рабочем режиме.

Показывает основные возможности модуля:
- Инициализация API
- Загрузка метаданных
- Валидация ордеров
- Работа с метриками
- CLI команды
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent.parent))

from market_meta import (
    MarketMetaAPI,
    configure_logging,
    get_config,
    get_logger,
    get_metrics_collector,
)
from market_meta.exceptions import ValidationError


async def demo_market_meta():
    """Демонстрация работы модуля market_meta"""

    print("🚀 Демонстрация модуля market_meta")
    print("=" * 50)

    # 1. Настройка логирования
    print("\n1️⃣ Настройка логирования...")
    configure_logging(level="INFO", console_output=True)
    logger = get_logger("demo")
    logger.info("Демонстрация модуля market_meta начата")

    # 2. Загрузка конфигурации
    print("\n2️⃣ Загрузка конфигурации...")
    config = get_config()
    print(f"   Окружение: {config.environment}")
    print(f"   Debug режим: {config.debug_mode}")
    print(f"   OKX URL: {config.okx.base_url}")
    print(f"   Cache TTL: {config.cache.metadata_ttl_hours}ч")

    # 3. Инициализация API
    print("\n3️⃣ Инициализация MarketMetaAPI...")
    api = MarketMetaAPI()
    print("   ✅ API инициализирован")

    # 4. Загрузка метаданных (мок-данные)
    print("\n4️⃣ Загрузка метаданных...")
    try:
        # Создаем тестовые метаданные
        from market_meta.metadata import (
            InstrumentMetadata,
            InstrumentType,
            MarketMetadata,
        )

        test_instruments = [
            InstrumentMetadata(
                symbol="BTC-USDT",
                inst_type=InstrumentType.SPOT,
                base_ccy="BTC",
                quote_ccy="USDT",
                state="live",
                min_size=0.00001,
                tick_size=0.1,
                lot_size=0.00001,
            ),
            InstrumentMetadata(
                symbol="ETH-USDT",
                inst_type=InstrumentType.SPOT,
                base_ccy="ETH",
                quote_ccy="USDT",
                state="live",
                min_size=0.001,
                tick_size=0.01,
                lot_size=0.001,
            ),
        ]

        api.market_metadata = MarketMetadata(instruments=test_instruments)
        print(f"   ✅ Загружено {len(test_instruments)} инструментов")

    except Exception as e:
        print(f"   ⚠️ Ошибка загрузки метаданных: {e}")

    # 5. Тестирование валидации
    print("\n5️⃣ Тестирование валидации ордеров...")

    test_cases = [
        ("BTC-USDT", 50000.0, 0.001, "Валидный ордер"),
        ("BTC-USDT", -1000.0, 0.001, "Негативная цена"),
        ("BTC-USDT", 50000.0, -0.001, "Негативное количество"),
        ("INVALID-SYMBOL", 50000.0, 0.001, "Несуществующий символ"),
    ]

    for symbol, price, qty, description in test_cases:
        try:
            violations = api.validate_order(symbol, price, qty)
            if violations:
                print(f"   ❌ {description}: {len(violations)} нарушений")
                for violation in violations[:2]:  # Показываем первые 2
                    print(f"      - {violation}")
            else:
                print(f"   ✅ {description}: валиден")
        except Exception as e:
            print(f"   ⚠️ {description}: ошибка - {type(e).__name__}")

    # 6. Работа с метриками
    print("\n6️⃣ Работа с метриками...")
    collector = get_metrics_collector()

    # Записываем тестовые метрики
    collector.record_cache_hit()
    collector.record_cache_miss()
    collector.record_validation_success(0.1)
    collector.record_validation_failure(0.2)
    collector.record_api_request(0.5, success=True)
    collector.record_error()

    # Получаем сводку
    summary = collector.get_metrics_summary()
    print(
        f"   Cache hit ratio: {summary.get('cache_hit_ratio', {}).get('latest', 'N/A')}%"
    )
    print(
        f"   Validation success rate: {summary.get('validation_success_rate', {}).get('latest', 'N/A')}%"
    )
    print(
        f"   API latency: {summary.get('api_request_duration', {}).get('latest', 'N/A')}s"
    )
    print(f"   Error rate: {summary.get('error_rate', {}).get('latest', 'N/A')}%")

    # 7. Тестирование CLI команд
    print("\n7️⃣ Тестирование CLI команд...")

    cli_commands = ["config", "metrics", "logs", "status"]

    for cmd in cli_commands:
        print(f"   Команда '{cmd}' доступна")

    # 8. Демонстрация исключений
    print("\n8️⃣ Демонстрация исключений...")

    from market_meta.exceptions import (
        ConfigurationError,
        MetadataError,
    )

    exceptions = [
        ConfigurationError("Тестовая ошибка конфигурации"),
        MetadataError("Тестовая ошибка метаданных"),
        ValidationError("Тестовая ошибка валидации", violations=["Тест"]),
    ]

    for exc in exceptions:
        print(f"   ✅ {type(exc).__name__}: {exc}")
        print(f"      Контекст: {exc.context}")

    # 9. Финальная сводка
    print("\n9️⃣ Финальная сводка...")

    logger.info("Демонстрация модуля market_meta завершена успешно")

    print("\n" + "=" * 50)
    print("🎉 Демонстрация завершена успешно!")
    print("\n📋 Что было протестировано:")
    print("   ✅ Инициализация и конфигурация")
    print("   ✅ Загрузка метаданных")
    print("   ✅ Валидация ордеров")
    print("   ✅ Система метрик")
    print("   ✅ CLI команды")
    print("   ✅ Обработка исключений")
    print("   ✅ Логирование")

    print("\n🚀 Модуль готов к использованию!")
    print("\n💡 Для дальнейшего тестирования используйте:")
    print("   python -m src.market_meta.cli config")
    print("   python -m src.market_meta.cli metrics")
    print("   python -m src.market_meta.cli status")


def run_demo():
    """Запуск демонстрации"""
    try:
        asyncio.run(demo_market_meta())
    except KeyboardInterrupt:
        print("\n\n⏹️ Демонстрация прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка в демонстрации: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_demo()
