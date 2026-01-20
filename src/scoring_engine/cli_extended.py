#!/usr/bin/env python3
"""
CLI для тестирования расширенной конфигурации Scoring Engine
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.scoring_engine.compute import ScoringEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Тестирование расширенной конфигурации Scoring Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Тест с расширенной конфигурацией
  python -m src.scoring_engine.cli_extended --symbol BTC-USDT-SWAP --tf 1m --ts 1754218200 --config weights_extended.yaml

  # Сравнение с базовой конфигурацией
  python -m src.scoring_engine.cli_extended --symbol BTC-USDT-SWAP --tf 1m --ts 1754218200 --compare
        """,
    )

    parser.add_argument("--symbol", type=str, required=True, help="Символ для анализа")
    parser.add_argument("--tf", type=str, required=True, help="Таймфрейм")
    parser.add_argument("--ts", type=int, required=True, help="Timestamp")
    parser.add_argument(
        "--config",
        type=str,
        default="weights_extended.yaml",
        help="Путь к конфигурационному файлу",
    )
    parser.add_argument(
        "--compare", action="store_true", help="Сравнить с базовой конфигурацией"
    )
    parser.add_argument("--verbose", action="store_true", help="Подробный вывод")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.compare:
            # Сравнение конфигураций
            await compare_configurations(args.symbol, args.tf, args.ts)
        else:
            # Тест расширенной конфигурации
            await test_extended_config(args.symbol, args.tf, args.ts, args.config)

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        sys.exit(1)


async def test_extended_config(symbol: str, timeframe: str, ts: int, config_path: str):
    """Тестирует расширенную конфигурацию"""
    logger.info(
        f"🧪 Тестирование расширенной конфигурации для {symbol} {timeframe} {ts}"
    )

    # Создаем движок с расширенной конфигурацией
    config_file = Path(__file__).parent / config_path
    if not config_file.exists():
        logger.error(f"❌ Файл конфигурации не найден: {config_file}")
        return

    engine = ScoringEngine(config_path=str(config_file))

    # Вычисляем score
    result = await engine.compute_score(symbol, timeframe, ts)

    if result:
        print("\n✅ Score с расширенной конфигурацией:")
        print(f"Symbol: {result.symbol}")
        print(f"Timeframe: {result.timeframe}")
        print(f"Timestamp: {result.ts}")
        print(f"Score Raw: {result.score_raw:.4f}")
        print(f"Score Calibrated: {result.score_calibrated:.4f}")
        print(f"P(Win): {result.p_win:.4f}")
        print(f"Edge Net: {result.edge_net:.4f}")
        print(f"Confidence: {result.confidence:.4f}")
        print(f"Valid: {result.is_valid}")

        if result.reasons:
            print(f"Reasons: {result.reasons}")
    else:
        print("❌ Не удалось вычислить score")


async def compare_configurations(symbol: str, timeframe: str, ts: int):
    """Сравнивает базовую и расширенную конфигурации"""
    logger.info(f"🔄 Сравнение конфигураций для {symbol} {timeframe} {ts}")

    # Базовая конфигурация
    engine_basic = ScoringEngine()
    result_basic = await engine_basic.compute_score(symbol, timeframe, ts)

    # Расширенная конфигурация
    config_file = Path(__file__).parent / "weights_extended.yaml"
    engine_extended = ScoringEngine(config_path=str(config_file))
    result_extended = await engine_extended.compute_score(symbol, timeframe, ts)

    print("\n📊 Сравнение результатов:")
    print(f"{'Метрика':<20} {'Базовая':<12} {'Расширенная':<12} {'Разница':<12}")
    print("-" * 60)

    if result_basic and result_extended:
        metrics = [
            ("Score Raw", result_basic.score_raw, result_extended.score_raw),
            (
                "Score Calibrated",
                result_basic.score_calibrated,
                result_extended.score_calibrated,
            ),
            ("P(Win)", result_basic.p_win, result_extended.p_win),
            ("Edge Net", result_basic.edge_net, result_extended.edge_net),
            ("Confidence", result_basic.confidence, result_extended.confidence),
        ]

        for name, basic_val, extended_val in metrics:
            diff = extended_val - basic_val
            print(f"{name:<20} {basic_val:<12.4f} {extended_val:<12.4f} {diff:<12.4f}")

        print("\n📈 Анализ:")
        if result_extended.score_raw > result_basic.score_raw:
            print("✅ Расширенная конфигурация дает более высокий score")
        else:
            print("📉 Расширенная конфигурация дает более низкий score")

        if result_extended.confidence > result_basic.confidence:
            print("✅ Расширенная конфигурация дает более высокую уверенность")
        else:
            print("📉 Расширенная конфигурация дает более низкую уверенность")

    else:
        print("❌ Не удалось получить результаты для сравнения")


if __name__ == "__main__":
    asyncio.run(main())
