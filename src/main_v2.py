"""
Тонкая оболочка для совместимости: делегирует в новый CLI src/cli/main.py
"""

import argparse
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


# Функция run_all_migrations перенесена в src/cli/commands/migrate.py


# Функция get_symbols_timeframes перенесена в соответствующие CLI команды


# Функция validate_system_readiness перенесена в соответствующие CLI команды


# Функции update_instruments_from_api, update_market_metadata, calculate_features_new,
# save_features_to_db, validate_market_data, demo_new_modules перенесены в соответствующие CLI команды


# Парсер перенесён в src/cli/main.py


# Функции calculate_detailed_signals, calculate_scoring, calculate_recommendations
# перенесены в соответствующие CLI команды


def create_parser():
    """Создает парсер для main_v2.py"""
    parser = argparse.ArgumentParser(prog="main_v2", description="PKLPO Main v2")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Запустить полный пайплайн (migrate + swap-sync + mtf + signals)",
    )
    parser.add_argument(
        "--mtf", action="store_true", help="Запустить только MTF обработку"
    )
    parser.add_argument(
        "--signals", action="store_true", help="Запустить только генерацию сигналов"
    )
    parser.add_argument(
        "--symbols",
        "-s",
        nargs="+",
        default=["BTC-USDT", "ETH-USDT", "BNB-USDT"],
        help="Символы для MTF обработки",
    )
    parser.add_argument(
        "--timeframes",
        "-t",
        nargs="+",
        default=["15m", "5m"],
        help="Таймфреймы для MTF обработки",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Количество воркеров для MTF обработки",
    )
    parser.add_argument(
        "--verbose", "-V", action="store_true", help="Подробный вывод (DEBUG)"
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Тихий режим (только ошибки)"
    )
    return parser


def main():
    """
    Тонкая оболочка: делегирует в новый CLI src/cli/main.py
    Сохраняем совместимость текущей точки входа.
    """
    parser = create_parser()
    args = parser.parse_args()

    if args.mtf:
        # Запускаем только MTF обработку
        logger.info("🎯 Запуск MTF обработки через main_v2.py")
        import sys

        from src.cli.main import main as cli_main

        # Сохраняем оригинальные аргументы
        original_argv = sys.argv.copy()

        # Устанавливаем аргументы для mtf process
        sys.argv = ["pklpo", "mtf", "process"]
        sys.argv.extend(["--symbols", *args.symbols])
        sys.argv.extend(["--timeframes", *args.timeframes])
        sys.argv.extend(["--max-workers", str(args.workers)])

        if args.verbose:
            sys.argv.append("--verbose")
        elif args.quiet:
            sys.argv.append("--quiet")

        try:
            cli_main()
        finally:
            # Восстанавливаем оригинальные аргументы
            sys.argv = original_argv

    elif args.signals:
        # Запускаем только генерацию сигналов
        logger.info("🎯 Запуск генерации сигналов через main_v2.py")
        import sys

        from src.cli.main import main as cli_main

        # Сохраняем оригинальные аргументы
        original_argv = sys.argv.copy()

        # Устанавливаем аргументы для signals generate
        sys.argv = ["pklpo", "signals", "generate"]
        sys.argv.extend(["--symbols", *args.symbols])
        sys.argv.extend(["--timeframes", *args.timeframes])
        sys.argv.extend(["--workers", str(args.workers)])

        if args.verbose:
            sys.argv.append("--verbose")
        elif args.quiet:
            sys.argv.append("--quiet")

        try:
            cli_main()
        finally:
            # Восстанавливаем оригинальные аргументы
            sys.argv = original_argv

    elif args.all:
        # Запускаем полный пайплайн включая MTF и Signals
        logger.info(
            "🚀 Запуск полного пайплайна (migrate + swap-sync + mtf + signals) через main_v2.py"
        )
        import sys

        from src.cli.main import main as cli_main

        # Сохраняем оригинальные аргументы
        original_argv = sys.argv.copy()

        try:
            # 1. Миграции
            logger.info("📊 Шаг 1: Выполнение миграций...")
            sys.argv = ["pklpo", "migrate"]
            if args.verbose:
                sys.argv.append("--verbose")
            elif args.quiet:
                sys.argv.append("--quiet")
            cli_main()

            # 2. Синхронизация данных
            logger.info("📈 Шаг 2: Синхронизация данных...")
            sys.argv = ["pklpo", "swap-sync"]
            if args.verbose:
                sys.argv.append("--verbose")
            elif args.quiet:
                sys.argv.append("--quiet")
            cli_main()

            # 3. MTF обработка
            logger.info("🎯 Шаг 3: MTF обработка...")
            sys.argv = ["pklpo", "mtf", "process"]
            sys.argv.extend(["--symbols", *args.symbols])
            sys.argv.extend(["--timeframes", *args.timeframes])
            sys.argv.extend(["--max-workers", str(args.workers)])
            if args.verbose:
                sys.argv.append("--verbose")
            elif args.quiet:
                sys.argv.append("--quiet")
            cli_main()

            # 4. Генерация сигналов
            logger.info("📊 Шаг 4: Генерация сигналов...")
            sys.argv = ["pklpo", "signals", "generate"]
            sys.argv.extend(["--symbols", *args.symbols])
            sys.argv.extend(["--timeframes", *args.timeframes])
            sys.argv.extend(["--workers", str(args.workers)])
            if args.verbose:
                sys.argv.append("--verbose")
            elif args.quiet:
                sys.argv.append("--quiet")
            cli_main()

            logger.info("🎉 Полный пайплайн завершен успешно!")

        finally:
            # Восстанавливаем оригинальные аргументы
            sys.argv = original_argv
    else:
        # Обычный запуск CLI
        from src.cli.main import main as cli_main

        cli_main()


# Функция export_execution_stats перенесена в соответствующие CLI команды


if __name__ == "__main__":
    main()


# Запуск через новый CLI:
# python -m src.cli.main migrate
# python -m src.cli.main swap-sync
# python -m src.cli.main pipeline --all
# python -m src.cli.main mtf process --symbols BTC-USDT ETH-USDT --timeframes 15m 5m
# python -m src.cli.main mtf status
# python -m src.cli.main mtf health
# python -m src.cli.main mtf metrics
# python -m src.cli.main mtf test

# Запуск через main_v2.py:
# python src/main_v2.py --all  # Полный пайплайн (migrate + swap-sync + mtf)
# python src/main_v2.py --mtf  # Только MTF обработка
# python src/main_v2.py --mtf --symbols BTC-USDT ETH-USDT --timeframes 15m --workers 2
# python src/main_v2.py --all --verbose  # С подробным выводом
