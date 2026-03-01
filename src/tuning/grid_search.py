"""
Grid-search оптимизация порогов для торговых сигналов.
"""

import asyncio
import csv
import itertools
import json
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


class GridSearchOptimizer:
    """
    Оптимизатор параметров сигналов методом grid-search.
    """

    def __init__(self, commission: float = 0.0005):
        """
        Инициализация оптимизатора.

        Args:
            commission: Комиссия за сделку
        """
        self.commission = commission
        self.evaluator = SignalEvaluator(commission)
        setup_logging("grid_search.log")

        # Определяем сетку параметров для оптимизации
        self.parameter_grid = {
            "rsi_buy": [20, 25, 30, 35],
            "rsi_sell": [65, 70, 75, 80],
            "adx_threshold": [20, 25, 30, 35],
            "stoch_k_buy": [10, 15, 20, 25],
            "stoch_k_sell": [75, 80, 85, 90],
            "min_score_for_buy": [2, 3, 4, 5],
            "min_score_for_sell": [-5, -4, -3, -2],
        }

    async def optimize_parameters(
        self,
        symbols: list[str] | None = None,
        timeframe: str = "1m",
        days_back: int = 7,
        max_drawdown_limit: float = 20.0,
    ) -> dict:
        """
        Оптимизирует параметры сигналов методом grid-search.

        Args:
            symbols: Список символов для оптимизации (None = все)
            timeframe: Таймфрейм
            days_back: Период для бэктестинга
            max_drawdown_limit: Максимальная допустимая просадка

        Returns:
            Dict: Лучшие параметры и результаты
        """
        print("🚀 Начинаем grid-search оптимизацию параметров...")

        # Получаем список символов
        if symbols is None:
            symbols = await self._get_all_symbols()

        print(f"📊 Оптимизация для {len(symbols)} символов")

        # Генерируем все комбинации параметров
        param_combinations = self._generate_parameter_combinations()
        total_combinations = len(param_combinations)

        print(f"🔍 Всего комбинаций параметров: {total_combinations}")

        results = []
        best_result = None
        best_sharpe = -999

        # Тестируем каждую комбинацию
        for i, params in enumerate(param_combinations, 1):
            print(f"\n📈 Тест {i}/{total_combinations}: {params}")

            try:
                # Применяем параметры
                await self._apply_parameters(params)

                # Пересчитываем сигналы
                await self._recalculate_signals(symbols, timeframe)

                # Оцениваем качество
                evaluation = await self._evaluate_parameters(
                    symbols, timeframe, days_back
                )

                if evaluation:
                    # Проверяем ограничение по просадке
                    if evaluation["avg_max_drawdown"] <= max_drawdown_limit:
                        result = {
                            "parameters": params,
                            "evaluation": evaluation,
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
                print(f"❌ Ошибка при тестировании параметров: {e}")
                continue

        # Сохраняем результаты
        await self._save_results(results, best_result)

        print("\n✅ Оптимизация завершена!")
        print(f"📊 Протестировано комбинаций: {len(results)}")

        if best_result:
            print("🏆 Лучшие параметры:")
            for param, value in best_result["parameters"].items():
                print(f"   {param}: {value}")
            print(f"📈 Средний Sharpe: {best_result['evaluation']['avg_sharpe']:.2f}")
            print(
                f"📉 Средняя просадка: {best_result['evaluation']['avg_max_drawdown']:.2f}%"
            )

        return best_result

    def _generate_parameter_combinations(self) -> list[dict]:
        """Генерирует все комбинации параметров."""
        param_names = list(self.parameter_grid.keys())
        param_values = list(self.parameter_grid.values())

        combinations = []
        for values in itertools.product(*param_values):
            combination = dict(zip(param_names, values, strict=False))
            combinations.append(combination)

        return combinations

    async def _apply_parameters(self, params: dict):
        """Применяет параметры к конфигурации."""
        global THRESHOLDS  # Move global declaration to the beginning

        # Создаем временную конфигурацию
        temp_config = THRESHOLDS.copy()
        temp_config.update(params)

        # Сохраняем во временный файл
        temp_config_path = "temp_config.yaml"
        save_config({"thresholds": temp_config}, temp_config_path)

        # Здесь можно было бы перезагрузить конфигурацию в runtime
        # Пока просто обновляем глобальные переменные
        THRESHOLDS.update(params)

    async def _recalculate_signals(self, symbols: list[str], timeframe: str):
        """Пересчитывает сигналы с новыми параметрами."""
        calculator = SignalCalculator()

        async for session in get_async_session():
            try:
                for symbol in symbols:
                    await calculator.calculate_signals_for_symbol(
                        session, symbol, timeframe, recalculate=True
                    )
            finally:
                break

    async def _evaluate_parameters(
        self, symbols: list[str], timeframe: str, days_back: int
    ) -> dict:
        """Оценивает качество параметров."""
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
        json_filename = f"grid_search_results_{timestamp}.json"
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        # Сохраняем лучшие результаты в CSV
        csv_filename = f"grid_search_best_{timestamp}.csv"
        with open(csv_filename, "w", newline="", encoding="utf-8") as f:
            if results:
                fieldnames = [
                    *list(results[0]["parameters"].keys()),
                    "avg_sharpe",
                    "avg_pnl_percent",
                    "avg_max_drawdown",
                    "avg_win_rate",
                    "total_trades",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for result in results:
                    row = result["parameters"].copy()
                    row.update(result["evaluation"])
                    writer.writerow(row)

        # Сохраняем лучшие параметры в отдельный файл
        if best_result:
            best_params_filename = f"best_parameters_{timestamp}.yaml"
            save_config(
                {
                    "best_parameters": best_result["parameters"],
                    "evaluation": best_result["evaluation"],
                    "timestamp": best_result["timestamp"],
                },
                best_params_filename,
            )

        print("💾 Результаты сохранены:")
        print(f"   📄 Все результаты: {json_filename}")
        print(f"   📊 CSV с метриками: {csv_filename}")
        if best_result:
            print(f"   🏆 Лучшие параметры: {best_params_filename}")


async def main():
    """Основная функция для запуска оптимизации."""
    optimizer = GridSearchOptimizer()

    # Оптимизируем параметры
    best_result = await optimizer.optimize_parameters(
        symbols=["BTC-USDT", "ETH-USDT", "ADA-USDT"],  # Тестируем на популярных парах
        days_back=7,
        max_drawdown_limit=20.0,
    )

    if best_result:
        print("\n🎉 Оптимизация завершена успешно!")
        print("🏆 Лучшие параметры найдены и сохранены")
    else:
        print("\n❌ Не удалось найти подходящие параметры")


if __name__ == "__main__":
    asyncio.run(main())
