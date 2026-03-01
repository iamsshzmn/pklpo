"""
Скрипт для оптимизации параметров торговых сигналов.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from src.logging_config import setup_logging
from src.tuning.grid_search import GridSearchOptimizer
from src.tuning.opt_weights import WeightOptimizer


async def main():
    """Основная функция для оптимизации параметров."""
    setup_logging("optimize_parameters.log")

    print("🚀 Запуск оптимизации параметров сигналов...")

    # Тестовые символы для оптимизации
    test_symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT", "DOT-USDT", "LINK-USDT"]

    print(f"📊 Оптимизация для {len(test_symbols)} символов")
    print(f"🔧 Символы: {', '.join(test_symbols)}")

    # 1. Grid-search оптимизация порогов
    print("\n🔍 Этап 1: Grid-search оптимизация порогов...")
    grid_optimizer = GridSearchOptimizer(commission=0.0005)

    best_params = await grid_optimizer.optimize_parameters(
        symbols=test_symbols, timeframe="1m", days_back=7, max_drawdown_limit=20.0
    )

    if best_params:
        print("✅ Grid-search завершен успешно!")
        print("🏆 Лучшие параметры найдены")
    else:
        print("❌ Grid-search не дал результатов")

    # 2. Оптимизация весов
    print("\n⚖️ Этап 2: Оптимизация весов правил...")
    weight_optimizer = WeightOptimizer(commission=0.0005)

    best_weights = await weight_optimizer.optimize_weights(
        symbols=test_symbols,
        timeframe="1m",
        days_back=7,
        iterations=50,  # Меньше итераций для быстрого тестирования
        max_drawdown_limit=20.0,
    )

    if best_weights:
        print("✅ Оптимизация весов завершена успешно!")
        print("🏆 Лучшие веса найдены")
    else:
        print("❌ Оптимизация весов не дала результатов")

    # Итоговая сводка
    print("\n🎉 Оптимизация завершена!")
    if best_params:
        print("📋 Лучшие параметры сохранены в файл")
    if best_weights:
        print("⚖️ Лучшие веса сохранены в файл")

    print("\n💡 Следующие шаги:")
    print("   1. Проверьте файлы с результатами")
    print("   2. Примените лучшие параметры в конфигурации")
    print("   3. Пересчитайте сигналы с новыми параметрами")
    print("   4. Оцените качество обновленных сигналов")


if __name__ == "__main__":
    asyncio.run(main())
