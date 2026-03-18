#!/usr/bin/env python3
"""
Enhanced MTF CLI

Расширенный командный интерфейс для новой архитектуры MTF с командами для:
- Тестирования качества данных
- Проверки алертов
- Мониторинга выполнения
- Управления конфигурацией
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.logging import setup_logging
from src.mtf import (
    alert_manager,
    check_data_quality,
    config_manager,
    get_mtf_signals,
    mtf_config,
    run_mtf_analysis,
    run_tracker,
    test_alerts,
)


def setup_parser() -> argparse.ArgumentParser:
    """Настроить парсер аргументов"""
    parser = argparse.ArgumentParser(
        description="Enhanced MTF CLI - Промышленная система анализа мультитаймфреймовых сигналов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Запуск полного анализа
  python cli_enhanced.py run --symbol BTC-USDT

  # Проверка качества данных
  python cli_enhanced.py quality --symbol BTC-USDT

  # Получение сигналов
  python cli_enhanced.py signals --horizon intraday --limit 5

  # Тестирование алертов
  python cli_enhanced.py test-alerts

  # Мониторинг выполнения
  python cli_enhanced.py monitor --hours 24

  # Управление конфигурацией
  python cli_enhanced.py config --show
  python cli_enhanced.py config --save
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Команда run
    run_parser = subparsers.add_parser("run", help="Запуск MTF анализа")
    run_parser.add_argument("--symbol", type=str, help="Конкретный символ")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Только проверка без выполнения"
    )

    # Команда quality
    quality_parser = subparsers.add_parser("quality", help="Проверка качества данных")
    quality_parser.add_argument("--symbol", type=str, help="Конкретный символ")
    quality_parser.add_argument("--timeframe", type=str, help="Конкретный таймфрейм")
    quality_parser.add_argument(
        "--summary", action="store_true", help="Показать сводку"
    )

    # Команда signals
    signals_parser = subparsers.add_parser("signals", help="Получение сигналов")
    signals_parser.add_argument(
        "--horizon",
        type=str,
        choices=["intraday", "swing", "week"],
        help="Горизонт сигналов",
    )
    signals_parser.add_argument(
        "--limit", type=int, default=10, help="Максимальное количество сигналов"
    )

    # Команда test-alerts
    subparsers.add_parser("test-alerts", help="Тестирование системы алертов")

    # Команда monitor
    monitor_parser = subparsers.add_parser("monitor", help="Мониторинг выполнения")
    monitor_parser.add_argument(
        "--hours", type=int, default=24, help="Количество часов для анализа"
    )
    monitor_parser.add_argument(
        "--active", action="store_true", help="Показать только активные запуски"
    )

    # Команда config
    config_parser = subparsers.add_parser("config", help="Управление конфигурацией")
    config_parser.add_argument(
        "--show", action="store_true", help="Показать текущую конфигурацию"
    )
    config_parser.add_argument(
        "--save", action="store_true", help="Сохранить конфигурацию в файл"
    )
    config_parser.add_argument(
        "--validate", action="store_true", help="Валидировать конфигурацию"
    )

    # Команда status
    status_parser = subparsers.add_parser("status", help="Статус системы")
    status_parser.add_argument(
        "--detailed", action="store_true", help="Подробный статус"
    )

    return parser


async def cmd_run(args: argparse.Namespace):
    """Команда запуска MTF анализа"""
    print("🚀 Запуск MTF анализа...")
    if args.symbol:
        print(f"📊 Символ: {args.symbol}")
    if args.dry_run:
        print("🔍 Режим проверки (dry-run)")

    try:
        result = await run_mtf_analysis(args.symbol, args.dry_run)

        print("\n✅ Анализ завершен!")
        print(f"📈 Сигналы рынка: {result.get('market_signals', 0)}")
        print(f"📊 Swing возможности: {result.get('swing_opportunities', 0)}")
        print(f"⚡ Внутридневные сигналы: {result.get('intraday_signals', 0)}")

        if result.get("status") == "completed":
            print("🎉 Статус: Успешно")
        else:
            print(f"⚠️ Статус: {result.get('status', 'Неизвестно')}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


async def cmd_quality(args: argparse.Namespace):
    """Команда проверки качества данных"""
    print("🔍 Проверка качества данных...")

    try:
        if args.summary:
            print("📊 Получение сводки качества...")
            summary = await check_data_quality()

            print("\n📈 Сводка качества данных:")
            print(f"📊 Всего символов: {summary.get('total_symbols', 0)}")
            print(f"🎯 Общий статус: {summary.get('overall_status', 'unknown')}")

            print("\n📊 Статусы по категориям:")
            for status, count in summary.get("status_counts", {}).items():
                print(f"  {status}: {count}")

            if summary.get("symbols_by_status", {}).get("critical"):
                print("\n🚨 Критические проблемы:")
                for symbol in summary["symbols_by_status"]["critical"][:5]:
                    print(f"  - {symbol}")

        elif args.symbol:
            print(f"🔍 Проверка символа: {args.symbol}")
            metrics = await check_data_quality(args.symbol)

            print(f"\n📊 Качество данных для {args.symbol}:")
            print(f"🎯 Статус: {metrics.status.value}")
            print(f"⏰ Возраст данных: {metrics.data_age_minutes:.1f} мин")
            print(f"✅ Валидность: {metrics.valid_rate:.1%}")
            print(f"❌ NaN: {metrics.nan_rate:.1%}")

            if metrics.warnings:
                print("\n⚠️ Предупреждения:")
                for warning in metrics.warnings:
                    print(f"  - {warning}")

            if metrics.errors:
                print("\n❌ Ошибки:")
                for error in metrics.errors:
                    print(f"  - {error}")

        else:
            print("❌ Укажите --symbol или --summary")
            return 1

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


async def cmd_signals(args: argparse.Namespace):
    """Команда получения сигналов"""
    print("📊 Получение сигналов...")
    if args.horizon:
        print(f"🎯 Горизонт: {args.horizon}")
    print(f"📈 Лимит: {args.limit}")

    try:
        signals = await get_mtf_signals(args.horizon, args.limit)

        if not signals:
            print("📭 Сигналы не найдены")
            return 0

        print(f"\n📊 Найдено сигналов: {len(signals)}")
        print("\n🏆 Топ сигналы:")

        for i, signal in enumerate(signals[: args.limit], 1):
            side_text = (
                "LONG"
                if signal.get("side") == 1
                else "SHORT"
                if signal.get("side") == -1
                else "FLAT"
            )
            symbol = signal.get("symbol", "Unknown")
            score = signal.get("score", 0)
            horizon = signal.get("horizon", "Unknown")

            print(f"  {i}. {symbol} {horizon} {side_text} (score: {score:.3f})")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


async def cmd_test_alerts(args: argparse.Namespace):
    """Команда тестирования алертов"""
    print("🔔 Тестирование системы алертов...")

    try:
        results = await test_alerts()

        print("\n📊 Результаты тестирования:")
        for channel, success in results.items():
            status = "✅ OK" if success else "❌ FAIL"
            print(f"  {channel}: {status}")

        # Отправляем тестовый алерт
        print("\n📤 Отправка тестового алерта...")
        await alert_manager.send_info_alert(
            "Тест системы алертов",
            "Это тестовое сообщение для проверки работы системы алертов MTF",
            source="CLI Test",
        )
        print("✅ Тестовый алерт отправлен")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


async def cmd_monitor(args: argparse.Namespace):
    """Команда мониторинга выполнения"""
    print(f"📊 Мониторинг выполнения (последние {args.hours} часов)...")

    try:
        if args.active:
            active_runs = run_tracker.get_active_runs()
            print(f"\n🔄 Активные запуски: {len(active_runs)}")

            for run in active_runs:
                duration = run.duration or 0
                print(
                    f"  - {run.source} (run_id: {run.run_id[:8]}...) - {duration:.1f}с"
                )
        else:
            stats = run_tracker.get_run_stats(args.hours)
            print("\n📈 Статистика выполнения:")
            print(f"  Всего запусков: {stats.get('total_runs', 0)}")
            print(f"  Завершенных: {stats.get('completed_runs', 0)}")
            print(f"  Успешность: {stats.get('success_rate', 0):.1%}")
            print(f"  Средняя длительность: {stats.get('avg_duration', 0):.1f}с")
            print(f"  Обработано строк: {stats.get('total_rows_processed', 0)}")
            print(f"  Записано строк: {stats.get('total_rows_written', 0)}")
            print(f"  Ошибок: {stats.get('total_errors', 0)}")
            print(f"  Предупреждений: {stats.get('total_warnings', 0)}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


def cmd_config(args: argparse.Namespace):
    """Команда управления конфигурацией"""
    print("⚙️ Управление конфигурацией...")

    try:
        if args.show:
            print("\n📋 Текущая конфигурация:")
            print(f"  Версия: {mtf_config.version}")
            print(f"  Версия схемы: {mtf_config.schema_version}")
            print(f"  Таймфреймы: {', '.join(mtf_config.get_all_timeframes())}")
            print(f"  Режим консенсуса: {mtf_config.consensus.mode.value}")
            print(f"  Макс. размер позиции: {mtf_config.risk.max_position_size:.1%}")
            print(f"  Дневной лимит потерь: {mtf_config.risk.daily_loss_limit:.1%}")

        elif args.save:
            config_manager.save_config()
            print("✅ Конфигурация сохранена")

        elif args.validate:
            print("🔍 Валидация конфигурации...")
            try:
                config_manager._validate_config()
                print("✅ Конфигурация валидна")
            except Exception as e:
                print(f"❌ Ошибка валидации: {e}")
                return 1

        else:
            print("❌ Укажите --show, --save или --validate")
            return 1

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


async def cmd_status(args: argparse.Namespace):
    """Команда статуса системы"""
    print("📊 Статус системы MTF...")

    try:
        # Проверяем качество данных
        print("🔍 Проверка качества данных...")
        quality_summary = await check_data_quality()

        # Получаем статистику выполнения
        print("📈 Получение статистики выполнения...")
        run_stats = run_tracker.get_run_stats(24)

        # Проверяем алерты
        print("🔔 Проверка алертов...")
        alert_stats = alert_manager.get_alert_stats(24)

        print("\n🎯 Общий статус системы:")

        # Определяем общий статус
        overall_status = "🟢 OK"
        if quality_summary.get("overall_status") == "critical":
            overall_status = "🔴 CRITICAL"
        elif quality_summary.get("overall_status") == "warning":
            overall_status = "🟡 WARNING"

        print(f"  Статус: {overall_status}")
        print(f"  Качество данных: {quality_summary.get('overall_status', 'unknown')}")
        print(f"  Успешность выполнения: {run_stats.get('success_rate', 0):.1%}")
        print(f"  Активных алертов: {sum(alert_stats.values())}")

        if args.detailed:
            print("\n📊 Детальная информация:")
            print(
                f"  Символов с проблемами: {quality_summary.get('status_counts', {}).get('critical', 0)}"
            )
            print(f"  Запусков за 24ч: {run_stats.get('total_runs', 0)}")
            print(f"  Ошибок за 24ч: {run_stats.get('total_errors', 0)}")
            print(f"  Алертов за 24ч: {sum(alert_stats.values())}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


async def main():
    """Главная функция"""
    setup_logging("mtf_enhanced.log")

    parser = setup_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    print("🚀 Enhanced MTF CLI")
    print("=" * 50)

    try:
        if args.command == "run":
            return await cmd_run(args)
        if args.command == "quality":
            return await cmd_quality(args)
        if args.command == "signals":
            return await cmd_signals(args)
        if args.command == "test-alerts":
            return await cmd_test_alerts(args)
        if args.command == "monitor":
            return await cmd_monitor(args)
        if args.command == "config":
            return cmd_config(args)
        if args.command == "status":
            return await cmd_status(args)
        print(f"❌ Неизвестная команда: {args.command}")
        return 1

    except KeyboardInterrupt:
        print("\n⏹️ Прервано пользователем")
        return 1
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
