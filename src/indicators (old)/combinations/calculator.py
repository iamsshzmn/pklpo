#!/usr/bin/env python3
"""
Модуль для расчёта комбинаций технических индикаторов
Анализирует корреляции и взаимодействия между индикаторами
"""

import logging
from dataclasses import dataclass

import pandas as pd

from .analyzer import SignalAnalyzer
from .pairs import PAIRS
from .performance import PerformanceAnalyzer
from .quartets import QUARTETS
from .recommendations import RecommendationGenerator
from .trios import TRIOS

# Объединяем все комбинации
COMBINATIONS = {**PAIRS, **TRIOS, **QUARTETS}

logger = logging.getLogger(__name__)
# Настраиваем логгер для записи только в файл, а не в консоль
logger.setLevel(logging.DEBUG)
# Удаляем все существующие обработчики
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
# Добавляем только файловый обработчик
file_handler = logging.FileHandler("combinations_calculator.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


@dataclass
class CombinationResult:
    """Результат анализа комбинации индикаторов"""

    combination_name: str
    indicators: list[str]
    correlation_matrix: pd.DataFrame
    signal_strength: float
    conflict_count: int
    agreement_count: int
    recommendation: str
    timestamp: int


class CombinationCalculator:
    """Калькулятор комбинаций индикаторов"""

    def __init__(self):
        self.combinations = COMBINATIONS
        self.results_cache = {}

    def calculate_combination(
        self, df: pd.DataFrame, combination_name: str
    ) -> CombinationResult | None:
        """
        Рассчитывает анализ для конкретной комбинации индикаторов

        Args:
            df: DataFrame с индикаторами
            combination_name: Название комбинации из реестра

        Returns:
            CombinationResult или None если комбинация не найдена
        """
        if combination_name not in self.combinations:
            logger.debug(f"Комбинация {combination_name} не найдена в реестре")
            return None

        combination = self.combinations[combination_name]
        indicators = combination["indicators"]

        # Проверяем наличие всех индикаторов в DataFrame
        missing_indicators = [ind for ind in indicators if ind not in df.columns]
        if missing_indicators:
            logger.debug(f"Отсутствуют индикаторы: {missing_indicators}")
            return None

        # Выбираем только нужные колонки
        ind_df = df[indicators].copy()

        # Удаляем строки с NaN
        ind_df = ind_df.dropna()

        if len(ind_df) < 10:  # Минимум данных для анализа
            logger.debug(f"Недостаточно данных для анализа: {len(ind_df)} строк")
            return None

        # Рассчитываем корреляционную матрицу
        correlation_matrix = ind_df.corr()

        # Анализируем сигналы
        signal_analysis = self._analyze_signals(ind_df, combination)

        # Формируем рекомендацию
        recommendation = self._generate_recommendation(
            correlation_matrix, signal_analysis, combination
        )

        return CombinationResult(
            combination_name=combination_name,
            indicators=indicators,
            correlation_matrix=correlation_matrix,
            signal_strength=signal_analysis["strength"],
            conflict_count=signal_analysis["conflicts"],
            agreement_count=signal_analysis["agreements"],
            recommendation=recommendation,
            timestamp=df.index[-1] if len(df) > 0 else 0,
        )

    def _analyze_signals(self, df: pd.DataFrame, combination: dict) -> dict:
        """
        Анализирует сигналы индикаторов в комбинации

        Args:
            df: DataFrame с индикаторами
            combination: Конфигурация комбинации

        Returns:
            Словарь с результатами анализа
        """
        # Используем новый анализатор сигналов
        signals = SignalAnalyzer.analyze_all_signals(df)
        strength, agreements, conflicts = SignalAnalyzer.calculate_signal_strength(
            signals
        )

        return {
            "signals": signals,
            "strength": strength,
            "agreements": agreements,
            "conflicts": conflicts,
            "total": len(signals),
        }

    def _generate_recommendation(
        self, correlation_matrix: pd.DataFrame, signal_analysis: dict, combination: dict
    ) -> str:
        """
        Генерирует торговую рекомендацию на основе анализа

        Args:
            correlation_matrix: Корреляционная матрица
            signal_analysis: Результаты анализа сигналов
            combination: Конфигурация комбинации

        Returns:
            Текстовая рекомендация
        """
        strength = signal_analysis["strength"]
        conflicts = signal_analysis["conflicts"]

        return RecommendationGenerator.generate_signal_recommendation(
            strength, conflicts
        )

    def calculate_all_combinations(self, df: pd.DataFrame) -> list[CombinationResult]:
        """
        Рассчитывает все доступные комбинации

        Args:
            df: DataFrame с индикаторами

        Returns:
            Список результатов для всех комбинаций
        """
        results = []

        for combination_name in self.combinations:
            try:
                result = self.calculate_combination(df, combination_name)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Ошибка при расчёте комбинации {combination_name}: {e}")

        # Сортируем по силе сигнала
        results.sort(key=lambda x: x.signal_strength, reverse=True)

        return results

    def get_best_combinations(
        self, df: pd.DataFrame, limit: int = 5
    ) -> list[CombinationResult]:
        """
        Возвращает лучшие комбинации по силе сигнала

        Args:
            df: DataFrame с индикаторами
            limit: Количество лучших комбинаций

        Returns:
            Список лучших комбинаций
        """
        all_results = self.calculate_all_combinations(df)
        return all_results[:limit]

    def export_combination_analysis(
        self, results: list[CombinationResult]
    ) -> pd.DataFrame:
        """
        Экспортирует результаты анализа в DataFrame

        Args:
            results: Список результатов анализа

        Returns:
            DataFrame с результатами
        """
        data = []

        for result in results:
            data.append(
                {
                    "combination": result.combination_name,
                    "signal_strength": result.signal_strength,
                    "agreements": result.agreement_count,
                    "conflicts": result.conflict_count,
                    "recommendation": result.recommendation,
                    "indicators_count": len(result.indicators),
                }
            )

        return pd.DataFrame(data)


def analyze_combination_performance(
    df: pd.DataFrame, combination_name: str, lookback_periods: int = 100
) -> dict:
    """
    Анализирует производительность комбинации на исторических данных

    Args:
        df: DataFrame с индикаторами
        combination_name: Название комбинации
        lookback_periods: Количество периодов для анализа

    Returns:
        Словарь с метриками производительности
    """
    calculator = CombinationCalculator()

    if combination_name not in calculator.combinations:
        return {"error": f"Комбинация {combination_name} не найдена"}

    # Используем новый анализатор производительности
    return PerformanceAnalyzer.generate_performance_report(
        df, combination_name, calculator, lookback_periods
    )
