#!/usr/bin/env python3
"""
Модуль для генерации торговых рекомендаций на основе анализа комбинаций
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class RecommendationGenerator:
    """Генератор торговых рекомендаций"""

    @staticmethod
    def generate_signal_recommendation(strength: float, conflicts: int) -> str:
        """
        Генерирует рекомендацию на основе силы сигнала и конфликтов

        Args:
            strength: Сила сигнала (0-1)
            conflicts: Количество конфликтующих сигналов

        Returns:
            Текстовая рекомендация
        """
        if strength >= 0.8:
            if conflicts == 0:
                return "🟢 СИЛЬНЫЙ СИГНАЛ: Все индикаторы согласованы"
            return "🟡 СИЛЬНЫЙ СИГНАЛ: Преобладают согласованные сигналы"
        if strength >= 0.6:
            return "🟡 УМЕРЕННЫЙ СИГНАЛ: Большинство индикаторов согласованы"
        if strength >= 0.4:
            return "🟠 СЛАБЫЙ СИГНАЛ: Смешанные сигналы"
        return "🔴 КОНФЛИКТ: Индикаторы противоречат друг другу"

    @staticmethod
    def generate_trading_recommendation(
        signals: dict[str, str], strength: float
    ) -> str:
        """
        Генерирует конкретную торговую рекомендацию

        Args:
            signals: Словарь сигналов индикаторов
            strength: Сила сигнала

        Returns:
            Торговая рекомендация
        """
        if strength < 0.4:
            return "⏸️ ОЖИДАНИЕ: Недостаточно четких сигналов для торговли"

        # Анализируем преобладающие сигналы
        bullish_count = sum(
            1
            for signal in signals.values()
            if any(
                keyword in signal.lower()
                for keyword in ["бычий", "перепроданность", "растущий", "приток"]
            )
        )
        bearish_count = sum(
            1
            for signal in signals.values()
            if any(
                keyword in signal.lower()
                for keyword in ["медвежий", "перекупленность", "падающий", "отток"]
            )
        )

        if bullish_count > bearish_count:
            if strength >= 0.8:
                return "🚀 СИЛЬНАЯ ПОКУПКА: Все индикаторы указывают на рост"
            return "📈 ПОКУПКА: Большинство индикаторов благоприятны"
        if bearish_count > bullish_count:
            if strength >= 0.8:
                return "📉 СИЛЬНАЯ ПРОДАЖА: Все индикаторы указывают на падение"
            return "📊 ПРОДАЖА: Большинство индикаторов неблагоприятны"
        return "⚖️ НЕЙТРАЛЬНО: Смешанные сигналы, рекомендуется осторожность"

    @staticmethod
    def generate_risk_assessment(
        signals: dict[str, str], correlation_matrix: pd.DataFrame
    ) -> str:
        """
        Оценивает риск на основе сигналов и корреляций

        Args:
            signals: Словарь сигналов
            correlation_matrix: Корреляционная матрица

        Returns:
            Оценка риска
        """
        # Анализируем волатильность
        volatility_indicators = ["bbands", "bb_upper", "bb_lower"]
        has_volatility = any(ind in signals for ind in volatility_indicators)

        # Анализируем силу тренда
        trend_indicators = ["adx", "ema"]
        has_trend = any(ind in signals for ind in trend_indicators)

        # Анализируем объем
        volume_indicators = ["obv", "cmf"]
        has_volume = any(ind in signals for ind in volume_indicators)

        risk_factors = []

        if not has_volatility:
            risk_factors.append("отсутствие данных о волатильности")

        if not has_trend:
            risk_factors.append("неопределенность направления тренда")

        if not has_volume:
            risk_factors.append("отсутствие подтверждения объемом")

        # Анализируем корреляции
        if not correlation_matrix.empty:
            high_correlations = (correlation_matrix.abs() > 0.8).sum().sum()
            if high_correlations > len(correlation_matrix) * 2:
                risk_factors.append("высокая корреляция индикаторов")

        if not risk_factors:
            return "🟢 НИЗКИЙ РИСК: Все факторы учтены"
        if len(risk_factors) == 1:
            return f"🟡 УМЕРЕННЫЙ РИСК: {risk_factors[0]}"
        return f"🔴 ВЫСОКИЙ РИСК: {', '.join(risk_factors)}"

    @staticmethod
    def generate_timeframe_recommendation(
        timeframe: str, signals: dict[str, str]
    ) -> str:
        """
        Генерирует рекомендацию по таймфрейму

        Args:
            timeframe: Текущий таймфрейм
            signals: Словарь сигналов

        Returns:
            Рекомендация по таймфрейму
        """
        # Определяем тип сигналов
        trend_signals = sum(
            1
            for signal in signals.values()
            if any(keyword in signal.lower() for keyword in ["тренд", "adx", "ema"])
        )
        momentum_signals = sum(
            1
            for signal in signals.values()
            if any(keyword in signal.lower() for keyword in ["rsi", "macd", "stoch"])
        )

        if trend_signals > momentum_signals:
            if timeframe in ["1m", "5m"]:
                return "⏰ РЕКОМЕНДУЕТСЯ: Перейти на более высокий таймфрейм (15m, 1H)"
            if timeframe in ["15m", "1H"]:
                return "✅ ОПТИМАЛЬНЫЙ ТАЙМФРЕЙМ: Трендовые сигналы хорошо видны"
            return "📊 ДОЛГОСРОЧНЫЙ: Тренд подтвержден на старших таймфреймах"
        if timeframe in ["1Dutc", "1Wutc"]:
            return "⏰ РЕКОМЕНДУЕТСЯ: Перейти на более низкий таймфрейм (1H, 4H)"
        if timeframe in ["1H", "4H"]:
            return "✅ ОПТИМАЛЬНЫЙ ТАЙМФРЕЙМ: Импульсные сигналы хорошо видны"
        return "⚡ КРАТКОСРОЧНЫЙ: Импульсные сигналы активны"

    @classmethod
    def generate_comprehensive_recommendation(
        cls,
        signals: dict[str, str],
        strength: float,
        conflicts: int,
        correlation_matrix: pd.DataFrame,
        timeframe: str,
    ) -> dict[str, str]:
        """
        Генерирует комплексную рекомендацию

        Returns:
            Словарь с различными типами рекомендаций
        """
        return {
            "signal_strength": cls.generate_signal_recommendation(strength, conflicts),
            "trading_action": cls.generate_trading_recommendation(signals, strength),
            "risk_assessment": cls.generate_risk_assessment(
                signals, correlation_matrix
            ),
            "timeframe_advice": cls.generate_timeframe_recommendation(
                timeframe, signals
            ),
            "confidence_level": f"{strength:.1%} уверенности в сигнале",
        }
