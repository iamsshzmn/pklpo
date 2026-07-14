"""
CLI интерфейс для модуля торговых рекомендаций
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.trade_recommender.recommend import recommend_for_score

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Главная функция CLI"""
    import argparse

    parser = argparse.ArgumentParser(description="Генерация торговых рекомендаций")
    parser.add_argument("score_id", type=int, help="ID записи из score_results")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Не сохранять результат в БД (по умолчанию)",
    )
    parser.add_argument("--save", action="store_true", help="Сохранить результат в БД")
    parser.add_argument(
        "--json", action="store_true", help="Вывести результат в JSON формате"
    )

    args = parser.parse_args()

    # Определяем dry_run
    dry_run = not args.save

    logger.info(f"Генерация рекомендации для score_id={args.score_id}")
    logger.info(f"dry_run={dry_run}")

    try:
        # Генерируем рекомендацию
        result = await recommend_for_score(args.score_id, dry_run=dry_run)

        # Выводим результат
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print_recommendation(result)

    except KeyboardInterrupt:
        logger.info("Операция прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


def print_recommendation(result: dict):
    """Выводит рекомендацию в читаемом формате"""
    print("\n" + "=" * 60)
    print("📊 ТОРГОВАЯ РЕКОМЕНДАЦИЯ")
    print("=" * 60)

    status = result.get("status", "unknown")

    if status == "ready":
        print(f"✅ Статус: {status}")
        print(f"📈 Символ: {result.get('symbol', 'N/A')}")
        print(f"⏰ Таймфрейм: {result.get('timeframe', 'N/A')}")
        print(f"🎯 Направление: {result.get('direction', 'N/A')}")
        print(f"💰 Цена входа: {result.get('entry_price', 0):.6f}")
        print(f"🛑 Стоп-лосс: {result.get('stop_loss_price', 0):.6f}")
        print(f"🎉 Take-profit: {result.get('take_profit_price', 0):.6f}")
        print(f"📊 Размер позиции: {result.get('position_size', 0):.2f}")
        print(f"💵 Риск: ${result.get('risk_amount_usdt', 0):.2f}")
        print(f"⚡ Плечо: {result.get('leverage_used', 0):.2f}x")
        print(f"💎 Стоимость позиции: ${result.get('position_value_usdt', 0):.2f}")
        print(f"📋 Score ID: {result.get('score_id', 'N/A')}")
        print(f"🔧 ATR: {result.get('atr', 0):.6f}")
        print(f"📏 ATR множитель: {result.get('atr_multiplier', 0):.1f}")
        print(f"📈 R:R ratio: {result.get('rr_ratio', 0):.1f}")
        print(f"💼 Баланс: ${result.get('balance', 0):.2f}")
        print(f"⚠️  Риск %: {result.get('risk_pct', 0) * 100:.1f}%")
        print(f"🔍 Dry run: {result.get('dry_run', True)}")

    elif status == "rejected":
        print(f"❌ Статус: {status}")
        print(f"📝 Причина: {result.get('message', 'N/A')}")
        print(f"📈 Символ: {result.get('symbol', 'N/A')}")
        print(f"⏰ Таймфрейм: {result.get('timeframe', 'N/A')}")
        print(f"📋 Score ID: {result.get('score_id', 'N/A')}")

    elif status == "error":
        print(f"💥 Статус: {status}")
        print(f"❌ Ошибка: {result.get('message', 'N/A')}")
        print(f"📋 Score ID: {result.get('score_id', 'N/A')}")

    else:
        print(f"❓ Неизвестный статус: {status}")
        print(f"📄 Результат: {result}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
