"""
CLI интерфейс для детализированного калькулятора сигналов.
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

from .signal_calculator_detailed import SignalCalculatorDetailed


def create_parser() -> argparse.ArgumentParser:
    """
    Создает парсер аргументов командной строки.

    Returns:
        argparse.ArgumentParser: Парсер аргументов
    """
    parser = argparse.ArgumentParser(
        description="Детализированный калькулятор торговых сигналов"
    )

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

    parser.add_argument(
        "--limit", type=int, help="Ограничить количество записей для обработки"
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
    setup_logging("calc_detailed_signals.log")
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    try:
        # Создаем детализированный калькулятор сигналов
        calculator = SignalCalculatorDetailed()

        logger.info(f"Используется конфигурация: {args.config}")

        if args.all_symbols:
            # Получаем все символы из БД через прямой SQL
            from sqlalchemy import text

            async for session in get_async_session():
                query = text("SELECT DISTINCT symbol FROM indicators")
                result = await session.execute(query)
                symbols = [row[0] for row in result.fetchall()]

                logger.info(f"Найдено {len(symbols)} символов")

                total_signals = 0
                for symbol in symbols:
                    signals_count = await calculator.calculate_signals_for_symbol(
                        symbol, args.timeframe, args.recalculate, args.limit
                    )
                    total_signals += signals_count

                logger.info(f"Всего создано {total_signals} детализированных сигналов")
                break

        elif args.symbol:
            # Рассчитываем для конкретного символа
            signals_count = await calculator.calculate_signals_for_symbol(
                args.symbol, args.timeframe, args.recalculate, args.limit
            )
            logger.info(
                f"Создано {signals_count} детализированных сигналов для {args.symbol}"
            )

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
