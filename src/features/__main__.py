"""
Main entry point for features module CLI.

This allows running the features module as a Python package:
python -m src.features <command> [options]

Or redirect to main CLI for convenience:
python -m src.features --symbols BTC-USDT-SWAP --timeframes 1D --limit 100
"""

import importlib.util
import os
import sys

# Добавляем корень проекта в PYTHONPATH
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Проверяем, переданы ли аргументы features команды напрямую
# Если первый аргумент не является командой cli.py, перенаправляем в основной CLI
valid_commands = [
    "calculate",
    "save",
    "validate",
    "test-parquet",
    "test-database",
    "pipeline",
    "snapshots-list",
    "snapshots-show",
]

if len(sys.argv) > 1 and sys.argv[1] not in valid_commands:
    # Перенаправляем в основной CLI features команду
    import argparse
    import asyncio

    from src.cli.commands.features import handle

    # Создаём парсер для features команды
    parser = argparse.ArgumentParser(description="Features calculation CLI")
    parser.add_argument("--symbols", nargs="+", help="Символы для обработки")
    parser.add_argument("--timeframes", nargs="+", default=["1D"], help="Таймфреймы")
    parser.add_argument("--limit", type=int, default=None, help="Лимит баров")
    parser.add_argument("--features-debug", action="store_true", help="DEBUG логи")
    parser.add_argument("--debug", action="store_true", help="DEBUG логи (alias)")
    parser.add_argument("--backend", default="auto", help="Бэкенд расчёта")
    parser.add_argument("--specs", nargs="+", default=None, help="Список индикаторов")
    parser.add_argument("--normalize", action="store_true", help="Нормировка")
    parser.add_argument(
        "--normalize-window", type=int, default=20, help="Окно нормировки"
    )
    parser.add_argument(
        "--refill-incomplete", action="store_true", help="Пересчитать incomplete"
    )
    parser.add_argument(
        "--refill-null", nargs="+", default=None, help="Пересчитать NULL"
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry run")

    args = parser.parse_args()
    sys.exit(asyncio.run(handle(args)))

# Иначе используем cli/main.py интерфейс
cli_file_path = os.path.join(os.path.dirname(__file__), "cli", "main.py")
spec = importlib.util.spec_from_file_location("src.features.cli.main", cli_file_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Failed to load cli.py from {cli_file_path}")

cli_module = importlib.util.module_from_spec(spec)
cli_module.__package__ = "src.features.cli"
cli_module.__name__ = "src.features.cli.main"
spec.loader.exec_module(cli_module)

main = cli_module.main

if __name__ == "__main__":
    sys.exit(main())
