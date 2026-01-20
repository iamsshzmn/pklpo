"""Numeric-only анализатор сигналов индикаторов."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_combinations_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_combinations_logger("analyzer")


class NumericSignalAnalyzer:
    """Анализатор сигналов с числовым выводом."""

    @staticmethod
    def analyze_all_signals_numeric(
        row: pd.Series, df: pd.DataFrame
    ) -> dict[str, float]:
        """
        Анализирует все сигналы и возвращает numeric features.

        Returns:
            Словарь с числовыми фичами
        """
        features: dict[str, float] = {}

        # RSI
        if "rsi14" in row.index:
            features.update(NumericSignalAnalyzer.analyze_rsi_numeric(row))

        # MACD
        if "macd" in row.index:
            features.update(NumericSignalAnalyzer.analyze_macd_numeric(row))

        # EMA
        ema_cols = [col for col in row.index if col.startswith("ema")]
        if ema_cols:
            features.update(NumericSignalAnalyzer.analyze_ema_numeric(row, ema_cols))

        # Bollinger Bands
        if all(col in row.index for col in ["bb_upper", "bb_middle", "bb_lower"]):
            features.update(NumericSignalAnalyzer.analyze_bbands_numeric(row))

        # Stochastic
        if "stoch_k" in row.index and "stoch_d" in row.index:
            features.update(NumericSignalAnalyzer.analyze_stoch_numeric(row))

        # ADX
        if "adx14" in row.index:
            features.update(NumericSignalAnalyzer.analyze_adx_numeric(row))

        # Volume indicators
        if "obv" in row.index:
            features.update(NumericSignalAnalyzer.analyze_obv_numeric(row, df))

        if "cmf" in row.index:
            features.update(NumericSignalAnalyzer.analyze_cmf_numeric(row))

        return features

    @staticmethod
    def analyze_rsi_numeric(row: pd.Series) -> dict[str, float]:
        """RSI → numeric features."""
        rsi = row["rsi14"]
        features: dict[str, float] = {}

        # Overbought/oversold scores (0-1)
        if rsi > 70:
            features["rsi_overbought_score"] = min(1.0, (rsi - 70) / 30.0)
            features["rsi_oversold_score"] = 0.0
        elif rsi < 30:
            features["rsi_overbought_score"] = 0.0
            features["rsi_oversold_score"] = min(1.0, (30 - rsi) / 30.0)
        else:
            features["rsi_overbought_score"] = 0.0
            features["rsi_oversold_score"] = 0.0

        # Normalized RSI (0-1)
        features["rsi_normalized"] = rsi / 100.0

        # Direction hint: >50 = bullish, <50 = bearish
        features["rsi_direction_hint"] = 1.0 if rsi > 50 else -1.0

        return features

    @staticmethod
    def analyze_macd_numeric(row: pd.Series) -> dict[str, float]:
        """MACD → numeric features."""
        macd = row.get("macd", 0.0)
        macd_signal = row.get("macd_signal", 0.0)
        macd_hist = row.get("macd_histogram", 0.0)

        features: dict[str, float] = {}

        # Direction: 1 = bullish, -1 = bearish, 0 = neutral
        if macd > 0:
            features["macd_direction_num"] = 1.0
        elif macd < 0:
            features["macd_direction_num"] = -1.0
        else:
            features["macd_direction_num"] = 0.0

        # MACD vs Signal
        if macd > macd_signal:
            features["macd_above_signal"] = 1.0
        else:
            features["macd_above_signal"] = 0.0

        # Histogram strength (normalized)
        if macd_hist != 0:
            features["macd_histogram_strength"] = min(1.0, abs(macd_hist) / 100.0)
        else:
            features["macd_histogram_strength"] = 0.0

        return features

    @staticmethod
    def analyze_ema_numeric(row: pd.Series, ema_cols: list[str]) -> dict[str, float]:
        """EMA → numeric features."""
        features: dict[str, float] = {}

        if len(ema_cols) < 2:
            return features

        ema_values = [row[col] for col in ema_cols if col in row.index]

        if len(ema_values) < 2:
            return features

        # Проверяем порядок (бычий = возрастающий)
        is_bullish = all(
            ema_values[i] >= ema_values[i + 1] for i in range(len(ema_values) - 1)
        )
        is_bearish = all(
            ema_values[i] <= ema_values[i + 1] for i in range(len(ema_values) - 1)
        )

        if is_bullish:
            features["ema_trend_direction"] = 1.0
        elif is_bearish:
            features["ema_trend_direction"] = -1.0
        else:
            features["ema_trend_direction"] = 0.0

        # Разница между первой и последней EMA (normalized)
        if ema_values[0] > 0:
            diff_pct = (ema_values[0] - ema_values[-1]) / ema_values[0]
            features["ema_spread_normalized"] = float(diff_pct)

        return features

    @staticmethod
    def analyze_bbands_numeric(row: pd.Series) -> dict[str, float]:
        """Bollinger Bands → numeric features."""
        features: dict[str, float] = {}

        close = row.get("close", 0.0)
        bb_upper = row.get("bb_upper", 0.0)
        bb_lower = row.get("bb_lower", 0.0)

        if bb_upper == 0 or bb_lower == 0:
            return features

        # Позиция относительно полос (0-1, где 0 = нижняя, 1 = верхняя)
        band_width = bb_upper - bb_lower
        if band_width > 0:
            position = (close - bb_lower) / band_width
            features["bb_position"] = float(position)

            # Выход за границы
            if close > bb_upper:
                features["bb_above_upper"] = 1.0
                features["bb_below_lower"] = 0.0
            elif close < bb_lower:
                features["bb_above_upper"] = 0.0
                features["bb_below_lower"] = 1.0
            else:
                features["bb_above_upper"] = 0.0
                features["bb_below_lower"] = 0.0

        return features

    @staticmethod
    def analyze_stoch_numeric(row: pd.Series) -> dict[str, float]:
        """Stochastic → numeric features."""
        stoch_k = row.get("stoch_k", 50.0)
        stoch_d = row.get("stoch_d", 50.0)

        features: dict[str, float] = {}

        # Overbought/oversold scores
        if stoch_k > 80:
            features["stoch_overbought_score"] = min(1.0, (stoch_k - 80) / 20.0)
        else:
            features["stoch_overbought_score"] = 0.0

        if stoch_k < 20:
            features["stoch_oversold_score"] = min(1.0, (20 - stoch_k) / 20.0)
        else:
            features["stoch_oversold_score"] = 0.0

        # Normalized values
        features["stoch_k_normalized"] = stoch_k / 100.0
        features["stoch_d_normalized"] = stoch_d / 100.0

        # Crossover
        if stoch_k > stoch_d:
            features["stoch_crossover"] = 1.0  # bullish
        else:
            features["stoch_crossover"] = -1.0  # bearish

        return features

    @staticmethod
    def analyze_adx_numeric(row: pd.Series) -> dict[str, float]:
        """ADX → numeric features."""
        adx = row.get("adx14", 0.0)

        features: dict[str, float] = {}

        # Trend strength (0-1)
        if adx >= 25:
            features["adx_trend_strength"] = min(1.0, adx / 50.0)
        else:
            features["adx_trend_strength"] = adx / 25.0

        # Strong trend flag
        features["adx_strong_trend"] = 1.0 if adx >= 25 else 0.0

        # Normalized ADX
        features["adx_normalized"] = adx / 100.0

        return features

    @staticmethod
    def analyze_obv_numeric(row: pd.Series, df: pd.DataFrame) -> dict[str, float]:
        """OBV → numeric features."""
        features: dict[str, float] = {}

        if "obv" not in row.index or len(df) < 2:
            return features

        current_obv = row["obv"]
        prev_obv = df.iloc[-2]["obv"] if len(df) >= 2 else current_obv

        # Direction
        if current_obv > prev_obv:
            features["obv_direction"] = 1.0
        elif current_obv < prev_obv:
            features["obv_direction"] = -1.0
        else:
            features["obv_direction"] = 0.0

        # Change rate (normalized)
        if prev_obv != 0:
            change_rate = (current_obv - prev_obv) / abs(prev_obv)
            features["obv_change_rate"] = float(change_rate)

        return features

    @staticmethod
    def analyze_cmf_numeric(row: pd.Series) -> dict[str, float]:
        """CMF → numeric features."""
        cmf = row.get("cmf", 0.0)

        features: dict[str, float] = {}

        # Direction
        if cmf > 0:
            features["cmf_direction"] = 1.0  # buying pressure
        elif cmf < 0:
            features["cmf_direction"] = -1.0  # selling pressure
        else:
            features["cmf_direction"] = 0.0

        # Strength (normalized to 0-1)
        features["cmf_strength"] = min(1.0, abs(cmf) * 2.0)

        return features
