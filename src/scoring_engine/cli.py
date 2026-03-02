"""
CLI интерфейс для Scoring Engine
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from .compute import compute_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Scoring Engine CLI (использует расширенную конфигурацию с 50+ индикаторами)"
    )
    parser.add_argument(
        "--symbol", required=True, help="Торговая пара (например, BTC-USDT)"
    )
    parser.add_argument(
        "--tf", "--timeframe", required=True, help="Таймфрейм (например, 1m, 5m, 1h)"
    )
    parser.add_argument(
        "--ts",
        type=int,
        help="Timestamp в секундах (если не указан, используется текущее время)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Определяем timestamp
    ts = args.ts if args.ts else int(datetime.utcnow().timestamp())

    logger.info(f"Вычисляем score для {args.symbol} {args.tf} {ts}")

    try:
        # Вычисляем score
        result = await compute_score(args.symbol, args.tf, ts)

        if result:
            print("\n✅ Score вычислен успешно:")
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
                print(f"Reasons: {', '.join(result.reasons)}")
        else:
            print(f"❌ Не удалось вычислить score для {args.symbol} {args.tf} {ts}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Ошибка при выполнении: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
