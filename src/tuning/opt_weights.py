"""
Оптимизация весов правил для торговых сигналов.
"""

import asyncio
import json
import random
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.backtest.evaluate import SignalEvaluator
from src.database import get_async_session
from src.logging_config import setup_logging
from src.signals.calculator import SignalCalculator
from src.signals.config import save_config


class WeightOptimizer:
    """
    Оптимизатор весов правил методом random search.
    """

    def __init__(self, commission: float = 0.0005):
        """
        Инициализация оптимизатора весов.

        Args:
            commission: Комиссия за сделку
        """
        self.commission = commission
        self.evaluator = SignalEvaluator(commission)
        setup_logging("weight_optimization.log")

        # Диапазоны весов для каждого правила
        self.weight_ranges = {
            "ema21_sma50": (0.5, 2.0),
            "sma50_sma200": (1.0, 3.0),  # Более важный
            "macd": (0.8, 2.0),
            "adx14": (0.8, 2.0),
            "ichimoku": (0.8, 2.0),
            "rsi14": (0.5, 2.0),
            "bollinger": (0.5, 2.0),
            "stochastic": (0.5, 2.0),
            "keltner": (0.5, 2.0),
            "obv_cmf": (0.3, 1.5),  # Менее важный
        }

    async def optimize_weights(
        self,
        symbols: list[str] | None = None,
        timeframe: str = "1m",
        days_back: int = 7,
        iterations: int = 100,
        max_drawdown_limit: float = 20.0,
    ) -> dict:
        """
        Оптимизирует веса правил методом random search.

        Args:
            symbols: Список символов для оптимизации
            timeframe: Таймфрейм
            days_back: Период для бэктестинга
            iterations: Количество итераций оптимизации
            max_drawdown_limit: Максимальная допустимая просадка

        Returns:
            Dict: Лучшие веса и результаты
        """
        print("🚀 Начинаем оптимизацию весов правил...")

        # Получаем список символов
        if symbols is None:
            symbols = await self._get_all_symbols()

        print(f"📊 Оптимизация для {len(symbols)} символов")
        print(f"🔄 Количество итераций: {iterations}")

        results = []
        best_result = None
        best_sharpe = -999

        # Выполняем итерации оптимизации
        for i in range(iterations):
            print(f"\n📈 Итерация {i+1}/{iterations}")

            try:
                # Генерируем случайные веса
                weights = self._generate_random_weights()
                print(f"🔧 Тестируем веса: {weights}")

                # Применяем веса
                await self._apply_weights(weights)

                # Пересчитываем сигналы
                await self._recalculate_signals(symbols, timeframe)

                # Оцениваем качество
                evaluation = await self._evaluate_weights(symbols, timeframe, days_back)

                if evaluation:
                    # Проверяем ограничение по просадке
                    if evaluation["avg_max_drawdown"] <= max_drawdown_limit:
                        result = {
                            "weights": weights,
                            "evaluation": evaluation,
                            "iteration": i + 1,
                            "timestamp": datetime.now().isoformat(),
                        }
                        results.append(result)

                        # Обновляем лучший результат
                        if evaluation["avg_sharpe"] > best_sharpe:
                            best_sharpe = evaluation["avg_sharpe"]
                            best_result = result
                            print(
                                f"🏆 Новый лучший результат! Sharpe: {best_sharpe:.2f}"
                            )

            except Exception as e:
                print(f"❌ Ошибка при итерации {i+1}: {e}")
                continue

        # Сохраняем результаты
        await self._save_results(results, best_result)

        print("\n✅ Оптимизация завершена!")
        print(f"📊 Успешных итераций: {len(results)}")

        if best_result:
            print("🏆 Лучшие веса:")
            for rule, weight in best_result["weights"].items():
                print(f"   {rule}: {weight:.2f}")
            print(f"📈 Средний Sharpe: {best_result['evaluation']['avg_sharpe']:.2f}")
            print(
                f"📉 Средняя просадка: {best_result['evaluation']['avg_max_drawdown']:.2f}%"
            )

        return best_result

    def _generate_random_weights(self) -> dict[str, float]:
        """Генерирует случайные веса в заданных диапазонах."""
        weights = {}

        for rule, (min_weight, max_weight) in self.weight_ranges.items():
            # Генерируем случайный вес с нормальным распределением
            weight = random.uniform(min_weight, max_weight)
            weights[rule] = round(weight, 2)

        return weights

    async def _apply_weights(self, weights: dict[str, float]):
        """Применяет веса к конфигурации."""
        # Обновляем глобальные веса
        global RULE_WEIGHTS
        RULE_WEIGHTS.update(weights)

        # Сохраняем во временный файл
        temp_config = {"rule_weights": weights}
        temp_config_path = "temp_weights.yaml"
        save_config(temp_config, temp_config_path)

    async def _recalculate_signals(self, symbols: list[str], timeframe: str):
        """Пересчитывает сигналы с новыми весами."""
        calculator = SignalCalculator()

        async for session in get_async_session():
            try:
                for symbol in symbols:
                    await calculator.calculate_signals_for_symbol(
                        session, symbol, timeframe, recalculate=True
                    )
            finally:
                break

    async def _evaluate_weights(
        self, symbols: list[str], timeframe: str, days_back: int
    ) -> dict:
        """Оценивает качество весов."""
        results = []

        for symbol in symbols:
            result = await self.evaluator.evaluate_symbol(symbol, timeframe, days_back)
            if result:
                results.append(result)

        if not results:
            return None

        # Вычисляем средние метрики
        return {
            "avg_sharpe": sum(r["sharpe_ratio"] for r in results) / len(results),
            "avg_pnl_percent": sum(r["total_pnl_percent"] for r in results)
            / len(results),
            "avg_max_drawdown": sum(r["max_drawdown"] for r in results) / len(results),
            "avg_win_rate": sum(r["win_rate"] for r in results) / len(results),
            "total_trades": sum(r["total_trades"] for r in results),
            "symbols_count": len(results),
        }

    async def _get_all_symbols(self) -> list[str]:
        """Получает список всех символов с данными."""
        async for session in get_async_session():
            try:
                from sqlalchemy import text

                query = text("SELECT DISTINCT symbol FROM ohlcv ORDER BY symbol")
                result = await session.execute(query)
                return [row.symbol for row in result.fetchall()]
            finally:
                break
        return []

    async def _save_results(self, results: list[dict], best_result: dict):
        """Сохраняет результаты оптимизации."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Сохраняем все результаты в JSON
        json_filename = f"weight_optimization_results_{timestamp}.json"
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        # Сохраняем лучшие веса в отдельный файл
        if best_result:
            best_weights_filename = f"best_weights_{timestamp}.yaml"
            save_config(
                {
                    "best_weights": best_result["weights"],
                    "evaluation": best_result["evaluation"],
                    "iteration": best_result["iteration"],
                    "timestamp": best_result["timestamp"],
                },
                best_weights_filename,
            )

        print("💾 Результаты сохранены:")
        print(f"   📄 Все результаты: {json_filename}")
        if best_result:
            print(f"   🏆 Лучшие веса: {best_weights_filename}")


async def main():
    """Основная функция для запуска оптимизации весов."""
    optimizer = WeightOptimizer()

    # Оптимизируем веса
    best_result = await optimizer.optimize_weights(
        symbols=["BTC-USDT", "ETH-USDT", "ADA-USDT"],
        days_back=7,
        iterations=50,  # Меньше итераций для быстрого тестирования
        max_drawdown_limit=20.0,
    )

    if best_result:
        print("\n🎉 Оптимизация весов завершена успешно!")
        print("🏆 Лучшие веса найдены и сохранены")
    else:
        print("\n❌ Не удалось найти подходящие веса")


if __name__ == "__main__":
    asyncio.run(main())
