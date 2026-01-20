#!/usr/bin/env python3
"""
CLI для расширенной MTF системы

Команды для управления расширенной MTF архитектурой:
- Загрузка контекстных данных
- Загрузка триггерных данных
- Запись финальных решений
- Просмотр результатов
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import get_async_session
from src.mtf.etl.consensus_writer import consensus_writer
from src.mtf.etl.context_loader import context_loader
from src.mtf.etl.trigger_loader import trigger_loader

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def load_context(args):
    """Загружает контекстные данные"""
    logger.info("🔄 Загрузка контекстных данных...")

    if args.symbol:
        success = await context_loader.load_context_for_symbol(
            args.symbol, args.max_age
        )
        if success:
            logger.info(f"✅ Контекст загружен для {args.symbol}")
        else:
            logger.error(f"❌ Ошибка загрузки контекста для {args.symbol}")
    else:
        results = await context_loader.load_context_for_all_symbols(args.max_age)
        success_count = sum(results.values())
        total_count = len(results)
        logger.info(f"✅ Контекст загружен: {success_count}/{total_count} символов")


async def load_triggers(args):
    """Загружает триггерные данные"""
    logger.info("🔄 Загрузка триггерных данных...")

    if args.symbol:
        success = await trigger_loader.load_triggers_for_symbol(
            args.symbol, args.max_age
        )
        if success:
            logger.info(f"✅ Триггеры загружены для {args.symbol}")
        else:
            logger.error(f"❌ Ошибка загрузки триггеров для {args.symbol}")
    else:
        results = await trigger_loader.load_triggers_for_all_symbols(args.max_age)
        success_count = sum(results.values())
        total_count = len(results)
        logger.info(f"✅ Триггеры загружены: {success_count}/{total_count} символов")


async def write_consensus(args):
    """Записывает финальные решения consensus"""
    logger.info("🔄 Запись финальных решений consensus...")

    horizons = args.horizons.split(",") if args.horizons else None

    if args.symbol:
        success = await consensus_writer.write_consensus_for_symbol(
            args.symbol, horizons
        )
        if success:
            logger.info(f"✅ Consensus записан для {args.symbol}")
        else:
            logger.error(f"❌ Ошибка записи consensus для {args.symbol}")
    else:
        results = await consensus_writer.write_consensus_for_all_symbols(horizons)
        success_count = sum(results.values())
        total_count = len(results)
        logger.info(f"✅ Consensus записан: {success_count}/{total_count} символов")


async def show_candidates(args):
    """Показывает топ кандидатов"""
    logger.info("📊 Показ топ кандидатов...")

    async for session in get_async_session():
        # Определяем представление в зависимости от горизонта
        view_name = f"mtf.top_{args.horizon}"

        # Базовый запрос
        query = f"""
            SELECT symbol, horizon, ts, side, score,
                   input_data->>'context_score' as context_score,
                   input_data->>'bias' as bias,
                   input_data->>'p15_up' as p15_up,
                   input_data->>'p15_down' as p15_down
            FROM {view_name}
        """

        # Добавляем фильтры
        conditions = []
        params = {}

        if args.side and args.side != "all":
            side_map = {"long": 1, "short": -1}
            conditions.append("side = :side")
            params["side"] = side_map.get(args.side, 0)

        if args.min_score:
            conditions.append("score >= :min_score")
            params["min_score"] = args.min_score

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY score DESC LIMIT {args.limit}"

        result = await session.execute(text(query), params)
        rows = result.fetchall()

        if not rows:
            logger.info("Нет кандидатов, соответствующих критериям")
            return

        # Выводим результаты
        print(f"\n🏆 Топ кандидаты ({args.horizon}, {args.side}):")
        print("=" * 120)
        print(
            f"{'Символ':<12} {'Сторона':<8} {'Score':<8} {'Context':<10} {'Bias':<8} {'P15 Up':<8} {'P15 Down':<10} {'Время'}"
        )
        print("-" * 120)

        for row in rows:
            side_str = (
                "LONG" if row.side == 1 else "SHORT" if row.side == -1 else "FLAT"
            )
            print(
                f"{row.symbol:<12} {side_str:<8} {row.score:<8.3f} {row.context_score:<10.3f} "
                f"{row.bias:<8} {row.p15_up:<8.3f} {row.p15_down:<10.3f} {row.ts}"
            )

        print("-" * 120)
        break


async def show_symbol_details(args):
    """Показывает детали по конкретному символу"""
    logger.info(f"📋 Детали для {args.symbol}...")

    async for session in get_async_session():
        # Получаем последние consensus данные
        query = text(
            """
            SELECT horizon, ts, side, score, input_data
            FROM mtf.consensus
            WHERE symbol = :symbol
            ORDER BY horizon, ts DESC
        """
        )

        result = await session.execute(query, {"symbol": args.symbol})
        consensus_rows = result.fetchall()

        if not consensus_rows:
            logger.info(f"Нет consensus данных для {args.symbol}")
            return

        print(f"\n📊 MTF Consensus для {args.symbol}:")
        print("=" * 80)

        for row in consensus_rows:
            side_str = (
                "LONG" if row.side == 1 else "SHORT" if row.side == -1 else "FLAT"
            )
            input_data = row.input_data

            print(f"\n🎯 {row.horizon.upper()}:")
            print(f"  Сторона: {side_str}")
            print(f"  Score: {row.score:.3f}")
            print(f"  Context Score: {input_data.get('context_score', 0):.3f}")
            print(f"  Bias: {input_data.get('bias', 'unknown')}")
            print(f"  P15 Up: {input_data.get('p15_up', 0):.3f}")
            print(f"  P15 Down: {input_data.get('p15_down', 0):.3f}")
            print(f"  P5 Up: {input_data.get('p5_up', 0):.3f}")
            print(f"  P5 Down: {input_data.get('p5_down', 0):.3f}")
            print(f"  Accel 5m: {input_data.get('accel_5m', 0)}")
            print(f"  Micro OK: {input_data.get('micro_ok', True)}")

        # Получаем контекстные данные
        query = text(
            """
            SELECT timeframe, score, valid, regime
            FROM mtf.context
            WHERE symbol = :symbol
            ORDER BY timeframe
        """
        )

        result = await session.execute(query, {"symbol": args.symbol})
        context_rows = result.fetchall()

        if context_rows:
            print("\n📈 Контекстные данные:")
            print("-" * 60)
            print(f"{'TF':<8} {'Score':<10} {'Valid':<8} {'Regime'}")
            print("-" * 60)

            for row in context_rows:
                print(
                    f"{row.timeframe:<8} {row.score:<10.3f} {row.valid!s:<8} {row.regime or 'N/A'}"
                )

        # Получаем триггерные данные
        query = text(
            """
            SELECT timeframe, p_up, p_down, accel, micro_ok
            FROM mtf.triggers
            WHERE symbol = :symbol
            ORDER BY timeframe
        """
        )

        result = await session.execute(query, {"symbol": args.symbol})
        trigger_rows = result.fetchall()

        if trigger_rows:
            print("\n⚡ Триггерные данные:")
            print("-" * 60)
            print(f"{'TF':<8} {'P Up':<8} {'P Down':<10} {'Accel':<8} {'Micro OK'}")
            print("-" * 60)

            for row in trigger_rows:
                print(
                    f"{row.timeframe:<8} {row.p_up:<8.3f} {row.p_down:<10.3f} "
                    f"{row.accel or 'N/A':<8} {str(row.micro_ok) if row.micro_ok is not None else 'N/A'}"
                )

        break


async def run_full_pipeline(args):
    """Запускает полный pipeline MTF"""
    logger.info("🚀 Запуск полного MTF pipeline...")

    # 1. Загружаем контекстные данные
    logger.info("📊 Шаг 1: Загрузка контекстных данных...")
    if args.symbol:
        success = await context_loader.load_context_for_symbol(
            args.symbol, args.max_age
        )
        if not success:
            logger.error("❌ Ошибка загрузки контекста")
            return
    else:
        results = await context_loader.load_context_for_all_symbols(args.max_age)
        success_count = sum(results.values())
        logger.info(f"✅ Контекст загружен: {success_count} символов")

    # 2. Загружаем триггерные данные
    logger.info("⚡ Шаг 2: Загрузка триггерных данных...")
    if args.symbol:
        success = await trigger_loader.load_triggers_for_symbol(
            args.symbol, args.max_age
        )
        if not success:
            logger.error("❌ Ошибка загрузки триггеров")
            return
    else:
        results = await trigger_loader.load_triggers_for_all_symbols(args.max_age)
        success_count = sum(results.values())
        logger.info(f"✅ Триггеры загружены: {success_count} символов")

    # 3. Записываем consensus
    logger.info("🎯 Шаг 3: Запись финальных решений...")
    horizons = args.horizons.split(",") if args.horizons else None
    if args.symbol:
        success = await consensus_writer.write_consensus_for_symbol(
            args.symbol, horizons
        )
        if not success:
            logger.error("❌ Ошибка записи consensus")
            return
    else:
        results = await consensus_writer.write_consensus_for_all_symbols(horizons)
        success_count = sum(results.values())
        logger.info(f"✅ Consensus записан: {success_count} символов")

    logger.info("✅ Полный MTF pipeline завершен успешно!")


def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(description="CLI для расширенной MTF системы")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Общие аргументы
    parser.add_argument(
        "--max-age", type=int, default=24, help="Максимальный возраст данных в часах"
    )

    # Команда загрузки контекста
    context_parser = subparsers.add_parser(
        "context", help="Загрузка контекстных данных"
    )
    context_parser.add_argument("--symbol", help="Конкретный символ (по умолчанию все)")

    # Команда загрузки триггеров
    triggers_parser = subparsers.add_parser(
        "triggers", help="Загрузка триггерных данных"
    )
    triggers_parser.add_argument(
        "--symbol", help="Конкретный символ (по умолчанию все)"
    )

    # Команда записи consensus
    consensus_parser = subparsers.add_parser(
        "consensus", help="Запись финальных решений"
    )
    consensus_parser.add_argument(
        "--symbol", help="Конкретный символ (по умолчанию все)"
    )
    consensus_parser.add_argument(
        "--horizons", help="Горизонты через запятую (intraday,swing,week)"
    )

    # Команда показа кандидатов
    candidates_parser = subparsers.add_parser(
        "candidates", help="Показать топ кандидатов"
    )
    candidates_parser.add_argument(
        "--horizon",
        choices=["intraday", "swing", "week"],
        default="intraday",
        help="Горизонт",
    )
    candidates_parser.add_argument(
        "--side", choices=["long", "short", "all"], default="all", help="Сторона"
    )
    candidates_parser.add_argument("--min-score", type=float, help="Минимальный score")
    candidates_parser.add_argument(
        "--limit", type=int, default=20, help="Количество результатов"
    )

    # Команда деталей символа
    details_parser = subparsers.add_parser("details", help="Детали по символу")
    details_parser.add_argument("--symbol", required=True, help="Символ для анализа")

    # Команда полного pipeline
    pipeline_parser = subparsers.add_parser("pipeline", help="Полный MTF pipeline")
    pipeline_parser.add_argument(
        "--symbol", help="Конкретный символ (по умолчанию все)"
    )
    pipeline_parser.add_argument(
        "--horizons", help="Горизонты через запятую (intraday,swing,week)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Выполняем команду
    try:
        if args.command == "context":
            asyncio.run(load_context(args))
        elif args.command == "triggers":
            asyncio.run(load_triggers(args))
        elif args.command == "consensus":
            asyncio.run(write_consensus(args))
        elif args.command == "candidates":
            asyncio.run(show_candidates(args))
        elif args.command == "details":
            asyncio.run(show_symbol_details(args))
        elif args.command == "pipeline":
            asyncio.run(run_full_pipeline(args))
        else:
            logger.error(f"Неизвестная команда: {args.command}")

    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Ошибка выполнения: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
