"""
MTF (Multi-Timeframe) CLI команды
Интеграция MTF System v3.0.0 в основной pipeline
"""

import argparse
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.mtf import MTFBuilder
from src.mtf.control.models import ControlConfig
from src.mtf.logging_config import get_main_logger

logger = get_main_logger()


def register(subparsers: argparse._SubParsersAction) -> None:
    """Регистрация MTF команд"""

    # Основная команда mtf
    mtf_parser = subparsers.add_parser(
        "mtf",
        help="MTF (Multi-Timeframe) System v3.0.0 - анализ рынка на множественных таймфреймах",
    )

    mtf_subparsers = mtf_parser.add_subparsers(dest="mtf_command", required=True)

    # Команда process - обработка символов
    process_parser = mtf_subparsers.add_parser(
        "process", help="Обработка символов через MTF pipeline"
    )
    process_parser.add_argument(
        "--symbols",
        "-s",
        nargs="+",
        default=["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        help="Список символов для обработки (по умолчанию: BTC-USDT ETH-USDT BNB-USDT)",
    )
    process_parser.add_argument(
        "--timeframes",
        "-t",
        nargs="+",
        default=["15m", "5m"],
        help="Список таймфреймов (по умолчанию: 15m 5m)",
    )
    process_parser.add_argument(
        "--max-workers",
        "-w",
        type=int,
        default=4,
        help="Максимальное количество воркеров для параллельной обработки (по умолчанию: 4)",
    )
    process_parser.add_argument(
        "--config", type=str, help="Путь к файлу конфигурации YAML"
    )
    process_parser.add_argument(
        "--use-real-data",
        action="store_true",
        default=True,
        help="Использовать реальные данные из базы данных (по умолчанию: True)",
    )
    process_parser.add_argument(
        "--use-test-data",
        action="store_true",
        help="Использовать тестовые данные вместо реальных",
    )
    process_parser.add_argument(
        "--database-url",
        help="URL подключения к базе данных (по умолчанию: из переменной окружения DATABASE_URL)",
    )
    process_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Подробный вывод"
    )
    process_parser.add_argument(
        "--quiet", "-q", action="store_true", help="Тихий режим (только ошибки)"
    )
    process_parser.set_defaults(_handler=handle_process)

    # Команда status - статус системы
    status_parser = mtf_subparsers.add_parser(
        "status", help="Получение статуса MTF системы"
    )
    status_parser.set_defaults(_handler=handle_status)

    # Команда health - проверка здоровья
    health_parser = mtf_subparsers.add_parser(
        "health", help="Проверка здоровья MTF системы"
    )
    health_parser.set_defaults(_handler=handle_health)

    # Команда metrics - метрики системы
    metrics_parser = mtf_subparsers.add_parser(
        "metrics", help="Получение метрик MTF системы"
    )
    metrics_parser.set_defaults(_handler=handle_metrics)

    # Команда test - тестирование системы
    test_parser = mtf_subparsers.add_parser(
        "test", help="Запуск полного теста MTF системы"
    )
    test_parser.add_argument(
        "--symbols",
        "-s",
        nargs="+",
        default=["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        help="Список символов для тестирования",
    )
    test_parser.add_argument(
        "--timeframes",
        "-t",
        nargs="+",
        default=["15m"],
        help="Список таймфреймов для тестирования",
    )
    test_parser.set_defaults(_handler=handle_test)

    # Команда results - получение результатов из БД
    results_parser = mtf_subparsers.add_parser(
        "results", help="Получение результатов MTF анализа из базы данных"
    )
    results_parser.add_argument(
        "--symbols",
        "-s",
        nargs="+",
        help="Список символов для получения результатов (по умолчанию: все)",
    )
    results_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=10,
        help="Максимальное количество результатов (по умолчанию: 10)",
    )
    results_parser.add_argument("--database-url", help="URL подключения к базе данных")
    results_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Подробный вывод"
    )
    results_parser.set_defaults(_handler=handle_results)


async def handle_process(args) -> None:
    """Обработка символов через MTF pipeline"""
    logger.info("MTF: Запуск обработки символов...")
    logger.info(f"Символы: {args.symbols}")
    logger.info(f"Таймфреймы: {args.timeframes}")
    logger.info(f"Воркеры: {args.max_workers}")

    try:
        # Создание конфигурации
        config = ControlConfig(
            max_workers=args.max_workers,
            context_enabled=True,
            triggers_enabled=True,
            consensus_enabled=True,
            pipeline_enabled=True,
            integration_enabled=True,
            enable_monitoring=True,
            enable_alerts=True,
        )

        # Получение URL базы данных
        database_url = getattr(args, "database_url", None) or os.getenv("DATABASE_URL")

        # Инициализация и обработка
        async with MTFBuilder(config, database_url) as mtf:
            logger.info("MTF система инициализирована")

            # Определяем, использовать ли реальные данные
            use_real_data = not getattr(args, "use_test_data", False)

            if use_real_data:
                logger.info("Используем реальные данные из базы данных")
                features_data = None  # Будет загружено автоматически
            else:
                logger.info("Используем тестовые данные")
                from test_mtf_full_system import create_test_features_data

                # Создание данных для всех символов
                features_data = {}
                for symbol in args.symbols:
                    features_data[symbol] = create_test_features_data(symbol, 100)
                    logger.info(f"Созданы тестовые данные для {symbol}")

            # Пакетная обработка
            logger.info("Начинаем пакетную обработку...")
            result = await mtf.process_batch(
                symbols=args.symbols,
                timeframes=args.timeframes,
                features_data=features_data,
                max_concurrent=args.max_workers,
                use_real_data=use_real_data,
            )

            # Вывод результатов
            logger.info("Результаты обработки:")
            logger.info(f"   - Всего символов: {result['total_symbols']}")
            logger.info(f"   - Успешных: {result['successful_symbols']}")
            logger.info(f"   - Неудачных: {result['failed_symbols']}")
            logger.info(f"   - Процент успеха: {result['success_rate']:.1%}")
            logger.info(
                f"   - Время обработки: {result['processing_time_seconds']:.3f}s"
            )

            # Детали по символам
            for symbol, symbol_result in result["results"].items():
                status = "OK" if symbol_result.get("success", False) else "FAIL"
                time_taken = symbol_result.get("processing_time_seconds", 0)
                logger.info(f"   - {symbol}: {status} ({time_taken:.3f}s)")

                if symbol_result.get("success", False):
                    pipeline_result = symbol_result.get("pipeline_result", {})
                    if pipeline_result:
                        context = pipeline_result.get("context")
                        triggers = pipeline_result.get("triggers")
                        consensus = pipeline_result.get("consensus")

                        if context:
                            logger.info(
                                f"     Context: score={getattr(context, 'overall_score', 0):.3f}, regime={getattr(context, 'dominant_regime', 'Unknown')}"
                            )
                        if triggers:
                            logger.info(
                                f"     Triggers: p_up={getattr(triggers, 'overall_p_up', 0):.3f}, p_down={getattr(triggers, 'overall_p_down', 0):.3f}"
                            )
                        if consensus:
                            logger.info(
                                f"     Consensus: type={getattr(consensus, 'consensus_type', 'Unknown')}, confidence={getattr(consensus, 'confidence_level', 'Unknown')}"
                            )

            logger.info("MTF обработка завершена успешно!")

    except Exception as e:
        logger.error(f"Ошибка MTF обработки: {e}")
        raise


async def handle_status(args) -> None:
    """Получение статуса MTF системы"""
    logger.info("Получение статуса MTF системы...")

    try:
        config = ControlConfig()
        async with MTFBuilder(config) as mtf:
            status = await mtf.get_system_status()

            logger.info("Статус системы получен:")
            logger.info(f"   - Статус: {status.get('system_status', 'Unknown')}")
            logger.info(f"   - Время работы: {status.get('uptime_seconds', 0):.2f}s")
            logger.info(f"   - Компоненты: {status.get('components', {})}")
            logger.info(
                f"   - Использование памяти: {status.get('memory_usage_mb', 0):.2f}MB"
            )
            logger.info(
                f"   - Использование CPU: {status.get('cpu_usage_percent', 0):.2f}%"
            )
            logger.info(f"   - Система здорова: {status.get('is_healthy', False)}")

    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        raise


async def handle_health(args) -> None:
    """Проверка здоровья MTF системы"""
    logger.info("Проверка здоровья MTF системы...")

    try:
        config = ControlConfig()
        async with MTFBuilder(config) as mtf:
            health = await mtf.health_check()

            logger.info("Проверка здоровья выполнена:")
            logger.info(f"   - Система здорова: {health.get('is_healthy', False)}")
            logger.info(
                f"   - Статус системы: {health.get('system_status', 'Unknown')}"
            )
            logger.info(
                f"   - Здоровье компонентов: {health.get('components_health', {})}"
            )
            logger.info(f"   - Количество ошибок: {health.get('error_count', 0)}")

    except Exception as e:
        logger.error(f"Ошибка проверки здоровья: {e}")
        raise


async def handle_metrics(args) -> None:
    """Получение метрик MTF системы"""
    logger.info("Получение метрик MTF системы...")

    try:
        config = ControlConfig()
        async with MTFBuilder(config) as mtf:
            metrics = await mtf.get_metrics()

            logger.info("Метрики получены:")
            if "metrics" in metrics:
                m = metrics["metrics"]
                logger.info(f"   - Всего запросов: {getattr(m, 'total_requests', 0)}")
                logger.info(f"   - Успешных: {getattr(m, 'successful_requests', 0)}")
                logger.info(f"   - Неудачных: {getattr(m, 'failed_requests', 0)}")
                logger.info(
                    f"   - Среднее время ответа: {getattr(m, 'avg_response_time', 0):.3f}s"
                )
                logger.info(
                    f"   - Время работы системы: {getattr(m, 'system_uptime', 0):.2f}s"
                )
                logger.info(
                    f"   - Готовых компонентов: {getattr(m, 'components_ready', 0)}"
                )
                logger.info(
                    f"   - Работающих компонентов: {getattr(m, 'components_running', 0)}"
                )
            else:
                logger.info(f"   - Метрики: {metrics}")

    except Exception as e:
        logger.error(f"Ошибка получения метрик: {e}")
        raise


async def handle_results(args) -> None:
    """Получение результатов MTF анализа из базы данных"""
    logger.info("Получение результатов MTF анализа...")

    try:
        # Получение URL базы данных
        database_url = getattr(args, "database_url", None) or os.getenv("DATABASE_URL")
        if not database_url:
            logger.error(
                "Database URL not provided. Use --database-url or set DATABASE_URL environment variable"
            )
            return

        # Инициализация MTF системы
        config = ControlConfig()
        async with MTFBuilder(config, database_url) as mtf:
            # Получение последних результатов
            latest_results = await mtf.get_latest_results(args.symbols)

            logger.info(f"Найдено результатов: {len(latest_results)}")

            if not latest_results:
                logger.info("Результаты не найдены")
                return

            # Ограничиваем количество результатов
            results_to_show = latest_results[: args.limit]

            logger.info("Последние результаты MTF анализа:")
            for i, result in enumerate(results_to_show, 1):
                logger.info(f"{i}. {result.symbol} ({', '.join(result.timeframes)})")
                logger.info(f"   - Время: {result.timestamp}")
                logger.info(
                    f"   - Режим: {result.dominant_regime} (уверенность: {result.regime_confidence:.3f})"
                )
                logger.info(f"   - Context Score: {result.context_score:.3f}")
                logger.info(
                    f"   - Triggers: p_up={result.overall_p_up:.3f}, p_down={result.overall_p_down:.3f}"
                )
                logger.info(f"   - Ускорение: {result.acceleration_type}")
                logger.info(f"   - Микро-фильтр: {'OK' if result.micro_ok else 'FAIL'}")
                logger.info(
                    f"   - Консенсус: {result.consensus_type} (уверенность: {result.confidence_level})"
                )
                logger.info(f"   - Consensus Score: {result.consensus_score:.3f}")
                logger.info(
                    f"   - Veto: {'Применен' if result.veto_applied else 'Не применен'}"
                )
                logger.info(f"   - Интеграция: {result.integration_status}")
                logger.info(
                    f"   - Время обработки: {result.total_processing_time_ms}ms"
                )
                logger.info("")

            if args.verbose and len(latest_results) > args.limit:
                logger.info(f"... и еще {len(latest_results) - args.limit} результатов")

            # Получение статистики
            statistics = await mtf.get_statistics(hours=24)
            if statistics:
                total_processed = sum(stat["total_processed"] for stat in statistics)
                total_successful = sum(stat["successful"] for stat in statistics)
                total_failed = sum(stat["failed"] for stat in statistics)

                logger.info("Статистика за последние 24 часа:")
                logger.info(f"   - Всего обработано: {total_processed}")
                logger.info(f"   - Успешно: {total_successful}")
                logger.info(f"   - Неудачно: {total_failed}")
                if total_processed > 0:
                    logger.info(
                        f"   - Процент успеха: {(total_successful/total_processed*100):.1f}%"
                    )

    except Exception as e:
        logger.error(f"Ошибка получения результатов: {e}")
        raise


async def handle_test(args) -> None:
    """Запуск полного теста MTF системы"""
    logger.info("Запуск полного теста MTF системы...")
    logger.info(f"Тестовые символы: {args.symbols}")
    logger.info(f"Тестовые таймфреймы: {args.timeframes}")

    try:
        # Импортируем и запускаем полный тест
        from test_mtf_full_system import test_mtf_full_system

        await test_mtf_full_system()

        logger.info("Полный тест MTF системы завершен успешно!")

    except Exception as e:
        logger.error(f"Ошибка тестирования: {e}")
        raise
