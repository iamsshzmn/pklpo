"""
CLI интерфейс для калькулятора сигналов.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from src.database import get_async_session
from src.logging_config import setup_logging

from ..engine import create_signal_engine
from .signal_calculator import SignalCalculator


def create_parser() -> argparse.ArgumentParser:
    """
    Создает парсер аргументов командной строки.

    Returns:
        argparse.ArgumentParser: Парсер аргументов
    """
    parser = argparse.ArgumentParser(description="Калькулятор торговых сигналов")

    parser.add_argument(
        "--symbol", "-s", type=str, help="Символ для расчета (например, BTC-USDT)"
    )

    parser.add_argument(
        "--timeframe", "-t", type=str, default="1m", help="Таймфрейм (по умолчанию: 1m)"
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="balanced",
        choices=["balanced", "conservative", "aggressive"],
        help="Конфигурация движка сигналов (по умолчанию: balanced)",
    )

    parser.add_argument(
        "--config-file", type=str, help="Путь к файлу конфигурации YAML"
    )

    parser.add_argument(
        "--recalculate",
        "-r",
        action="store_true",
        help="Пересчитать существующие сигналы",
    )

    parser.add_argument(
        "--all-symbols",
        action="store_true",
        help="Рассчитать сигналы для всех символов",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")

    return parser


async def main():
    """
    Основная функция CLI.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Настраиваем логирование
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging("calc_signals.log")  # Pass filename instead of log level
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)  # Set level on the specific logger

    try:
        # Создаем движок сигналов
        if args.config_file:
            from ..config import load_config

            load_config(args.config_file)
            logger.info(f"Загружена конфигурация из файла: {args.config_file}")
            # Здесь можно было бы создать движок с кастомной конфигурацией
            engine = create_signal_engine(args.config)
        else:
            engine = create_signal_engine(args.config)

        calculator = SignalCalculator(engine)

        logger.info(f"Используется конфигурация: {args.config}")

        async for session in get_async_session():
            if args.all_symbols:
                # Получаем все символы из БД через прямой SQL
                from sqlalchemy import text

                query = text("SELECT DISTINCT symbol FROM indicators")
                result = await session.execute(query)
                symbols = [row[0] for row in result.fetchall()]

                logger.info(f"Найдено {len(symbols)} символов")

                total_signals = 0
                for symbol in symbols:
                    signals_count = await calculator.calculate_signals_for_symbol(
                        session, symbol, args.timeframe, args.recalculate
                    )
                    total_signals += signals_count

                logger.info(f"Всего создано {total_signals} сигналов")

            elif args.symbol:
                # Рассчитываем для конкретного символа
                signals_count = await calculator.calculate_signals_for_symbol(
                    session, args.symbol, args.timeframe, args.recalculate
                )
                logger.info(f"Создано {signals_count} сигналов для {args.symbol}")

            else:
                parser.print_help()
                sys.exit(1)
            break  # Выходим после первого сеанса

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
