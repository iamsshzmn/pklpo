#!/usr/bin/env python3
"""
CLI для работы с комбинациями фичей (numeric-only версия).
"""

import argparse
import asyncio
import sys
from datetime import datetime

from src.utils.session_utils import get_db_session

from ..application.service import CombinationService
from ..infrastructure import (
    NumericCombinationCalculator,
    PostgresCombinationRepository,
    PostgresIndicatorProvider,
)
from ..logging_config import get_combinations_logger, setup_combinations_logging

logger = get_combinations_logger("cli")


async def cmd_compute(
    symbol: str,
    timeframes: list[str],
    start: datetime | None,
    end: datetime | None,
    limit: int | None,
) -> None:
    """Вычислить и сохранить комбинации фичей."""
    async with get_db_session() as session:
        # Создаём компоненты
        provider = PostgresIndicatorProvider(session)
        calculator = NumericCombinationCalculator()
        repository = PostgresCombinationRepository(session)

        service = CombinationService(
            provider=provider,
            calculator=calculator,
            repository=repository,
        )

        total_saved = 0
        for timeframe in timeframes:
            logger.info(f"Processing {symbol}/{timeframe}...")
            saved = await service.compute_and_save_for_range(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                limit=limit,
            )
            total_saved += saved
            logger.info(f"Saved {saved} rows for {symbol}/{timeframe}")

        logger.info(f"Total saved: {total_saved} rows")


async def cmd_compute_latest(
    symbol: str,
    timeframes: list[str],
    limit: int,
) -> None:
    """Вычислить и сохранить последние N комбинаций."""
    async with get_db_session() as session:
        provider = PostgresIndicatorProvider(session)
        calculator = NumericCombinationCalculator()
        repository = PostgresCombinationRepository(session)

        service = CombinationService(
            provider=provider,
            calculator=calculator,
            repository=repository,
        )

        total_saved = 0
        for timeframe in timeframes:
            logger.info(f"Processing {symbol}/{timeframe}...")
            saved = await service.compute_and_save_latest(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
            total_saved += saved
            logger.info(f"Saved {saved} rows for {symbol}/{timeframe}")

        logger.info(f"Total saved: {total_saved} rows")


def parse_datetime(date_str: str) -> datetime:
    """Парсинг даты из строки."""
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        # Пробуем другие форматы
        for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {date_str}") from None


def main() -> None:
    """Главная функция CLI."""
    # Настраиваем логирование
    setup_combinations_logging(level="INFO")

    parser = argparse.ArgumentParser(
        description="CLI для работы с комбинациями фичей (numeric-only)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Команды")

    # Команда compute
    compute_parser = subparsers.add_parser("compute", help="Вычислить комбинации")
    compute_parser.add_argument(
        "--symbol", required=True, help="Символ (например, BTC-USDT-SWAP)"
    )
    compute_parser.add_argument(
        "--timeframes",
        nargs="+",
        required=True,
        help="Таймфреймы (например, 1m 5m 15m)",
    )
    compute_parser.add_argument(
        "--start",
        type=str,
        help="Начало периода (ISO format или YYYY-MM-DD)",
    )
    compute_parser.add_argument(
        "--end",
        type=str,
        help="Конец периода (ISO format или YYYY-MM-DD)",
    )
    compute_parser.add_argument(
        "--limit",
        type=int,
        help="Максимальное количество строк",
    )

    # Команда compute-latest
    latest_parser = subparsers.add_parser(
        "compute-latest", help="Вычислить последние N комбинаций"
    )
    latest_parser.add_argument(
        "--symbol", required=True, help="Символ (например, BTC-USDT-SWAP)"
    )
    latest_parser.add_argument(
        "--timeframes",
        nargs="+",
        required=True,
        help="Таймфреймы (например, 1m 5m 15m)",
    )
    latest_parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Количество последних строк (по умолчанию 500)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "compute":
            start = parse_datetime(args.start) if args.start else None
            end = parse_datetime(args.end) if args.end else None
            asyncio.run(
                cmd_compute(
                    symbol=args.symbol,
                    timeframes=args.timeframes,
                    start=start,
                    end=end,
                    limit=args.limit,
                )
            )
        elif args.command == "compute-latest":
            asyncio.run(
                cmd_compute_latest(
                    symbol=args.symbol,
                    timeframes=args.timeframes,
                    limit=args.limit,
                )
            )
        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
