#!/usr/bin/env python3
"""
CLI для автоматического процессора Scoring Engine
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.scoring_engine.processor import (
    get_score_statistics,
    process_all_scores,
    process_symbol_scores,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Автоматический процессор Scoring Engine (расширенная конфигурация с 50+ индикаторами)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Обработать все доступные данные
  python -m src.scoring_engine.processor_cli --all

  # Обработать с лимитом
  python -m src.scoring_engine.processor_cli --all --limit 1000

  # Обработать конкретный символ
  python -m src.scoring_engine.processor_cli --symbol BTC-USDT-SWAP

  # Обработать символ с конкретным таймфреймом
  python -m src.scoring_engine.processor_cli --symbol BTC-USDT-SWAP --timeframe 1m

  # Показать статистику
  python -m src.scoring_engine.processor_cli --stats
        """,
    )

    # Основные команды
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all", action="store_true", help="Обработать все доступные данные"
    )
    group.add_argument("--symbol", type=str, help="Обработать конкретный символ")
    group.add_argument("--stats", action="store_true", help="Показать статистику")

    # Дополнительные параметры
    parser.add_argument(
        "--limit", type=int, help="Ограничение количества записей для обработки"
    )
    parser.add_argument(
        "--timeframe", type=str, help="Таймфрейм для обработки (если указан символ)"
    )
    parser.add_argument("--verbose", action="store_true", help="Подробный вывод")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.stats:
            # Показываем статистику
            logger.info("📊 Получаем статистику...")
            stats = await get_score_statistics()

            if stats:
                print("\n📈 Статистика Scoring Engine:")
                print(f"  Всего индикаторов: {stats.get('total_indicators', 0):,}")
                print(f"  Всего комбинаций: {stats.get('total_combinations', 0):,}")
                print(f"  Всего score: {stats.get('total_scores', 0):,}")
                print(f"  Score за последний час: {stats.get('recent_scores_1h', 0):,}")

                if stats.get("top_symbols"):
                    print("\n🏆 Топ символов по количеству score:")
                    for i, item in enumerate(stats["top_symbols"][:5], 1):
                        print(f"  {i}. {item['symbol']}: {item['count']:,}")
            else:
                print("❌ Не удалось получить статистику")

        elif args.all:
            # Обрабатываем все данные
            logger.info("🚀 Запуск обработки всех данных...")
            result = await process_all_scores(args.limit)

            print("\n✅ Результат обработки:")
            print(f"  Статус: {result.get('status', 'unknown')}")
            print(f"  Обработано: {result.get('processed', 0):,}")
            print(f"  Ошибок: {result.get('errors', 0):,}")
            print(f"  Время: {result.get('duration', 0):.1f}с")

            if result.get("status") == "completed":
                print("🎉 Обработка завершена успешно!")
            elif result.get("status") == "no_data":
                print("ℹ️ Нет данных для обработки")
            else:
                print("❌ Обработка завершена с ошибками")

        elif args.symbol:
            # Обрабатываем конкретный символ
            logger.info(f"🎯 Обработка символа {args.symbol}...")
            result = await process_symbol_scores(args.symbol, args.timeframe)

            print(f"\n✅ Результат обработки {args.symbol}:")
            print(f"  Статус: {result.get('status', 'unknown')}")
            print(f"  Обработано: {result.get('processed', 0):,}")
            print(f"  Ошибок: {result.get('errors', 0):,}")
            print(f"  Время: {result.get('duration', 0):.1f}с")

            if result.get("status") == "completed":
                print(f"🎉 Обработка {args.symbol} завершена успешно!")
            elif result.get("status") == "no_data":
                print(f"ℹ️ Нет данных для обработки {args.symbol}")
            else:
                print(f"❌ Обработка {args.symbol} завершена с ошибками")

    except KeyboardInterrupt:
        logger.info("⏹️ Обработка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
