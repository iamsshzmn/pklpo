#!/usr/bin/env python3
"""
Модуль для анализа производительности комбинаций индикаторов
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Анализатор производительности комбинаций"""

    @staticmethod
    def calculate_historical_signals(
        df: pd.DataFrame, combination_name: str, calculator, lookback_periods: int = 100
    ) -> list[dict]:
        """
        Рассчитывает исторические сигналы для комбинации

        Args:
            df: DataFrame с индикаторами
            combination_name: Название комбинации
            calculator: Калькулятор комбинаций
            lookback_periods: Количество периодов для анализа

        Returns:
            Список исторических сигналов
        """
        if combination_name not in calculator.combinations:
            return []

        # Берем последние периоды
        recent_df = df.tail(lookback_periods)

        if len(recent_df) < 10:
            return []

        signals = []
        # Простая мемоизация по индексу конца окна
        memo: dict[int, dict] = {}
        for i in range(10, len(recent_df)):
            period_df = recent_df.iloc[: i + 1]
            # Ключ мемоизации — позиция конца окна
            if i in memo:
                result = memo[i]
            else:
                result = calculator.calculate_combination(period_df, combination_name)
                if result:
                    memo[i] = result
            if result:
                signals.append(
                    {
                        "timestamp": result.timestamp,
                        "strength": result.signal_strength,
                        "recommendation": result.recommendation,
                        "agreements": result.agreement_count,
                        "conflicts": result.conflict_count,
                    }
                )

        return signals

    @staticmethod
    def analyze_signal_distribution(signals: list[dict]) -> dict:
        """
        Анализирует распределение сигналов по силе

        Args:
            signals: Список исторических сигналов

        Returns:
            Статистика распределения
        """
        if not signals:
            return {}

        strengths = [s["strength"] for s in signals]

        return {
            "total_signals": len(signals),
            "strong_signals": len([s for s in strengths if s >= 0.7]),
            "moderate_signals": len([s for s in strengths if 0.4 <= s < 0.7]),
            "weak_signals": len([s for s in strengths if s < 0.4]),
            "avg_strength": np.mean(strengths),
            "std_strength": np.std(strengths),
            "min_strength": np.min(strengths),
            "max_strength": np.max(strengths),
        }

    @staticmethod
    def calculate_success_rate(
        signals: list[dict], price_data: pd.DataFrame = None, threshold: float = 0.7
    ) -> dict:
        """
        Рассчитывает процент успешных сигналов

        Args:
            signals: Список сигналов
            price_data: Данные цен для проверки (опционально)
            threshold: Порог для сильных сигналов

        Returns:
            Статистика успешности
        """
        if not signals:
            return {}

        strong_signals = [s for s in signals if s["strength"] >= threshold]
        weak_signals = [s for s in signals if s["strength"] < threshold]

        # Если есть данные цен, можно добавить более сложную логику
        # пока используем простую статистику
        success_rate = len(strong_signals) / len(signals) if signals else 0

        return {
            "total_signals": len(signals),
            "strong_signals": len(strong_signals),
            "weak_signals": len(weak_signals),
            "success_rate": success_rate,
            "strong_signal_rate": len(strong_signals) / len(signals) if signals else 0,
        }

    @staticmethod
    def analyze_signal_consistency(signals: list[dict]) -> dict:
        """
        Анализирует консистентность сигналов

        Args:
            signals: Список сигналов

        Returns:
            Статистика консистентности
        """
        if len(signals) < 2:
            return {}

        # Анализируем изменения силы сигналов
        strength_changes = []
        for i in range(1, len(signals)):
            change = signals[i]["strength"] - signals[i - 1]["strength"]
            strength_changes.append(change)

        # Анализируем стабильность
        np.mean(np.abs(strength_changes))
        volatility = np.std(strength_changes)

        # Определяем тренд
        if len(strength_changes) > 0:
            trend = "улучшение" if np.mean(strength_changes) > 0 else "ухудшение"
        else:
            trend = "стабильно"

        return {
            "avg_strength_change": np.mean(strength_changes),
            "strength_volatility": volatility,
            "trend": trend,
            "stability_score": 1.0
            / (1.0 + volatility),  # Чем меньше волатильность, тем выше стабильность
        }

    @staticmethod
    def calculate_risk_metrics(signals: list[dict]) -> dict:
        """
        Рассчитывает метрики риска

        Args:
            signals: Список сигналов

        Returns:
            Метрики риска
        """
        if not signals:
            return {}

        strengths = [s["strength"] for s in signals]
        conflicts = [s["conflicts"] for s in signals]

        # Коэффициент вариации (мера относительной волатильности)
        cv = np.std(strengths) / np.mean(strengths) if np.mean(strengths) > 0 else 0

        # Среднее количество конфликтов
        avg_conflicts = np.mean(conflicts)

        # Максимальное падение силы сигнала
        max_drawdown = 0
        peak = strengths[0]
        for strength in strengths:
            if strength > peak:
                peak = strength
            drawdown = (peak - strength) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return {
            "coefficient_of_variation": cv,
            "avg_conflicts": avg_conflicts,
            "max_drawdown": max_drawdown,
            "risk_score": (cv + avg_conflicts / 10 + max_drawdown)
            / 3,  # Композитный риск
        }

    @classmethod
    def generate_performance_report(
        cls,
        df: pd.DataFrame,
        combination_name: str,
        calculator,
        lookback_periods: int = 100,
    ) -> dict:
        """
        Генерирует полный отчет о производительности

        Args:
            df: DataFrame с индикаторами
            combination_name: Название комбинации
            calculator: Калькулятор комбинаций
            lookback_periods: Количество периодов

        Returns:
            Полный отчет о производительности
        """
        # Получаем исторические сигналы
        signals = cls.calculate_historical_signals(
            df, combination_name, calculator, lookback_periods
        )

        if not signals:
            return {"error": "Не удалось рассчитать исторические сигналы"}

        # Анализируем различные аспекты
        distribution = cls.analyze_signal_distribution(signals)
        success = cls.calculate_success_rate(signals)
        consistency = cls.analyze_signal_consistency(signals)
        risk = cls.calculate_risk_metrics(signals)

        return {
            "combination_name": combination_name,
            "analysis_period": lookback_periods,
            "distribution": distribution,
            "success_metrics": success,
            "consistency": consistency,
            "risk_metrics": risk,
            "overall_score": cls._calculate_overall_score(
                distribution, success, consistency, risk
            ),
            "signals": signals,
        }

    @staticmethod
    def _calculate_overall_score(
        distribution: dict, success: dict, consistency: dict, risk: dict
    ) -> float:
        """
        Рассчитывает общий скор производительности

        Args:
            distribution: Статистика распределения
            success: Статистика успешности
            consistency: Статистика консистентности
            risk: Метрики риска

        Returns:
            Общий скор (0-1)
        """
        if not all([distribution, success, consistency, risk]):
            return 0.0

        # Веса для разных компонентов
        weights = {
            "success_rate": 0.4,
            "avg_strength": 0.3,
            "stability": 0.2,
            "risk": 0.1,
        }

        # Нормализуем компоненты
        success_score = success.get("success_rate", 0)
        strength_score = distribution.get("avg_strength", 0)
        stability_score = consistency.get("stability_score", 0)
        risk_score = 1.0 - risk.get("risk_score", 0)  # Инвертируем риск

        # Рассчитываем взвешенный скор
        overall_score = (
            success_score * weights["success_rate"]
            + strength_score * weights["avg_strength"]
            + stability_score * weights["stability"]
            + risk_score * weights["risk"]
        )

        return min(1.0, max(0.0, overall_score))
