#!/usr/bin/env python3
"""
Модуль для анализа сигналов индикаторов
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class SignalAnalyzer:
    """Анализатор сигналов индикаторов"""

    @staticmethod
    def analyze_rsi(df: pd.DataFrame) -> dict[str, str]:
        """Анализирует RSI сигналы"""
        if "rsi14" not in df.columns:
            return {}

        rsi = df.iloc[-1]["rsi14"]
        if rsi > 70:
            return {"rsi": "перекупленность"}
        if rsi < 30:
            return {"rsi": "перепроданность"}
        return {"rsi": "нейтрально"}

    @staticmethod
    def analyze_macd(df: pd.DataFrame) -> dict[str, str]:
        """Анализирует MACD сигналы"""
        if "macd" not in df.columns:
            return {}

        macd = df.iloc[-1]["macd"]
        if macd > 0:
            return {"macd": "бычий"}
        return {"macd": "медвежий"}

    @staticmethod
    def analyze_ema(df: pd.DataFrame) -> dict[str, str]:
        """Анализирует EMA сигналы"""
        ema_indicators = [col for col in df.columns if col.startswith("ema")]
        if len(ema_indicators) < 2:
            return {}

        latest = df.iloc[-1]
        ema_values = [latest[col] for col in ema_indicators]

        if all(ema_values[i] > ema_values[i + 1] for i in range(len(ema_values) - 1)):
            return {"ema": "бычий тренд"}
        if all(ema_values[i] < ema_values[i + 1] for i in range(len(ema_values) - 1)):
            return {"ema": "медвежий тренд"}
        return {"ema": "смешанный"}

    @staticmethod
    def analyze_bollinger_bands(df: pd.DataFrame) -> dict[str, str]:
        """Анализирует Bollinger Bands сигналы"""
        required_cols = ["bb_upper", "bb_middle", "bb_lower"]
        if not all(col in df.columns for col in required_cols):
            return {}

        latest = df.iloc[-1]
        close = df.iloc[-1].get("close", 0)
        bb_upper = latest["bb_upper"]
        bb_lower = latest["bb_lower"]

        if close > bb_upper:
            return {"bbands": "выше верхней полосы"}
        if close < bb_lower:
            return {"bbands": "ниже нижней полосы"}
        return {"bbands": "внутри полос"}

    @staticmethod
    def analyze_stochastic(df: pd.DataFrame) -> dict[str, str]:
        """Анализирует Stochastic сигналы"""
        if "stoch_k" not in df.columns or "stoch_d" not in df.columns:
            return {}

        latest = df.iloc[-1]
        stoch_k = latest["stoch_k"]
        stoch_d = latest["stoch_d"]

        if stoch_k > 80 and stoch_d > 80:
            return {"stoch": "перекупленность"}
        if stoch_k < 20 and stoch_d < 20:
            return {"stoch": "перепроданность"}
        return {"stoch": "нейтрально"}

    @staticmethod
    def analyze_adx(df: pd.DataFrame) -> dict[str, str]:
        """Анализирует ADX сигналы"""
        if "adx14" not in df.columns:
            return {}

        adx = df.iloc[-1]["adx14"]
        if adx > 25:
            return {"adx": "сильный тренд"}
        if adx > 20:
            return {"adx": "умеренный тренд"}
        return {"adx": "слабый тренд"}

    @staticmethod
    def analyze_volume(df: pd.DataFrame) -> dict[str, str]:
        """Анализирует объемные индикаторы"""
        signals = {}

        if "obv" in df.columns:
            obv = df.iloc[-1]["obv"]
            obv_prev = df.iloc[-2]["obv"] if len(df) > 1 else obv
            if obv > obv_prev:
                signals["obv"] = "растущий объем"
            else:
                signals["obv"] = "падающий объем"

        if "cmf" in df.columns:
            cmf = df.iloc[-1]["cmf"]
            if cmf > 0.1:
                signals["cmf"] = "сильный приток денег"
            elif cmf < -0.1:
                signals["cmf"] = "сильный отток денег"
            else:
                signals["cmf"] = "нейтральный денежный поток"

        return signals

    @classmethod
    def analyze_all_signals(cls, df: pd.DataFrame) -> dict[str, str]:
        """Анализирует все доступные сигналы"""
        signals = {}

        # Анализируем каждый тип индикаторов
        signals.update(cls.analyze_rsi(df))
        signals.update(cls.analyze_macd(df))
        signals.update(cls.analyze_ema(df))
        signals.update(cls.analyze_bollinger_bands(df))
        signals.update(cls.analyze_stochastic(df))
        signals.update(cls.analyze_adx(df))
        signals.update(cls.analyze_volume(df))

        return signals

    @staticmethod
    def calculate_signal_strength(signals: dict[str, str]) -> tuple[float, int, int]:
        """
        Рассчитывает силу сигнала, количество согласованных и конфликтующих сигналов

        Returns:
            (strength, agreements, conflicts)
        """
        if not signals:
            return 0.0, 0, 0

        # Определяем бычьи и медвежьи сигналы
        bullish_keywords = [
            "бычий",
            "перепроданность",
            "растущий",
            "приток",
            "сильный тренд",
        ]
        bearish_keywords = [
            "медвежий",
            "перекупленность",
            "падающий",
            "отток",
            "слабый тренд",
        ]

        bullish_signals = sum(
            1
            for signal in signals.values()
            if any(keyword in signal.lower() for keyword in bullish_keywords)
        )
        bearish_signals = sum(
            1
            for signal in signals.values()
            if any(keyword in signal.lower() for keyword in bearish_keywords)
        )

        # Определяем преобладающее направление
        if bullish_signals > bearish_signals:
            agreements = bullish_signals
            conflicts = bearish_signals
        else:
            agreements = bearish_signals
            conflicts = bullish_signals

        # Рассчитываем силу сигнала (0-1)
        total_signals = len(signals)
        strength = agreements / total_signals if total_signals > 0 else 0.0

        return strength, agreements, conflicts
