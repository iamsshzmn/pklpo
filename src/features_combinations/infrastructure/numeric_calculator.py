"""Numeric-only калькулятор комбинаций фичей."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from ..domain.models import CombinationRow
from ..domain.registry import COMBINATIONS
from ..logging_config import get_combinations_logger
from .numeric_analyzer import NumericSignalAnalyzer

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = get_combinations_logger("calculator")


class NumericCombinationCalculator:
    """Калькулятор комбинаций с числовыми фичами (numeric-only)."""

    def __init__(self) -> None:
        self.combinations = COMBINATIONS
        self.analyzer = NumericSignalAnalyzer()

    def calculate_for_df(
        self,
        symbol: str,
        timeframe: str,
        df_indicators: pd.DataFrame,
    ) -> Iterable[CombinationRow]:
        """
        Рассчитать комбинации фичей для DataFrame индикаторов.

        Yields:
            CombinationRow с числовыми фичами для каждой строки и комбинации
        """
        if df_indicators.empty:
            logger.warning(f"Empty indicators DataFrame for {symbol}/{timeframe}")
            return

        if "timestamp" not in df_indicators.columns:
            logger.error(
                f"timestamp column not found in DataFrame for {symbol}/{timeframe}"
            )
            return

        # Обрабатываем каждую комбинацию
        for combo_id, combo_config in self.combinations.items():
            indicators = combo_config["indicators"]

            # Проверяем наличие всех индикаторов
            missing = [ind for ind in indicators if ind not in df_indicators.columns]
            if missing:
                logger.debug(
                    f"Missing indicators for {combo_id}: {missing} "
                    f"(symbol={symbol}, timeframe={timeframe})"
                )
                continue

            # Обрабатываем каждую строку DataFrame
            for _, row in df_indicators.iterrows():
                # Пропускаем строки с NaN в нужных индикаторах
                if row[indicators].isna().any():
                    continue

                # Извлекаем timestamp
                timestamp = row["timestamp"]
                if isinstance(timestamp, int | float):
                    # Если timestamp в миллисекундах, преобразуем в datetime
                    try:
                        ts_dt = datetime.fromtimestamp(timestamp / 1000.0)
                    except (ValueError, OSError):
                        ts_dt = datetime.fromtimestamp(timestamp)
                else:
                    ts_dt = timestamp

                # Рассчитываем numeric features для этой строки
                features = self._calculate_numeric_features(
                    row, indicators, combo_id, df_indicators
                )

                if features:
                    yield CombinationRow(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=ts_dt,
                        combination_id=combo_id,
                        features=features,
                        meta=None,
                    )

    def _calculate_numeric_features(
        self,
        row: pd.Series,
        indicators: list[str],
        combo_id: str,
        df_indicators: pd.DataFrame,
    ) -> dict[str, float]:
        """
        Рассчитать числовые фичи для одной строки.

        Returns:
            Словарь с числовыми фичами
        """
        features: dict[str, float] = {}

        # Анализируем сигналы индикаторов (numeric)
        signal_features = self.analyzer.analyze_all_signals_numeric(row, df_indicators)

        # Добавляем базовые фичи из сигналов
        features.update(signal_features)

        # Рассчитываем корреляцию между индикаторами (если достаточно данных)
        if len(df_indicators) >= 10:
            try:
                corr_features = self._calculate_correlation_features(
                    df_indicators, indicators
                )
                features.update(corr_features)
            except Exception as e:
                logger.debug(f"Failed to calculate correlations: {e}")

        # Рассчитываем силу сигнала и направление
        strength, direction_num, agreements, conflicts = self._calculate_signal_metrics(
            signal_features
        )

        features["signal_strength"] = strength
        features["direction_num"] = direction_num
        features["agreement_count"] = float(agreements)
        features["conflict_count"] = float(conflicts)

        return features

    def _calculate_correlation_features(
        self, df: pd.DataFrame, indicators: list[str]
    ) -> dict[str, float]:
        """Рассчитать корреляционные фичи."""
        features: dict[str, float] = {}

        try:
            # Берем последние N строк для корреляции
            recent_df = df[indicators].tail(50).dropna()

            if len(recent_df) < 10:
                return features

            corr_matrix = recent_df.corr()

            # Средняя корреляция между индикаторами
            if len(indicators) > 1:
                corr_values = []
                for i in range(len(indicators)):
                    for j in range(i + 1, len(indicators)):
                        if (
                            indicators[i] in corr_matrix.index
                            and indicators[j] in corr_matrix.columns
                        ):
                            corr_val = corr_matrix.loc[indicators[i], indicators[j]]
                            if pd.notna(corr_val):
                                corr_values.append(float(corr_val))

                if corr_values:
                    features["avg_correlation"] = float(
                        sum(corr_values) / len(corr_values)
                    )
                    features["max_correlation"] = float(max(corr_values))
                    features["min_correlation"] = float(min(corr_values))

        except Exception as e:
            logger.debug(f"Correlation calculation error: {e}")

        return features

    def _calculate_signal_metrics(
        self, signal_features: dict[str, float]
    ) -> tuple[float, float, int, int]:
        """
        Рассчитать метрики сигнала из numeric features.

        Returns:
            (strength, direction_num, agreements, conflicts)
        """
        # Извлекаем direction_num из фичей
        direction_num = signal_features.get("direction_num", 0.0)

        # Считаем согласованные и конфликтующие сигналы
        bullish_signals = 0
        bearish_signals = 0

        # Проверяем различные индикаторы на направление
        for key, value in signal_features.items():
            if "direction" in key.lower() or "trend" in key.lower():
                if value > 0.5:
                    bullish_signals += 1
                elif value < -0.5:
                    bearish_signals += 1

        agreements = max(bullish_signals, bearish_signals)
        conflicts = min(bullish_signals, bearish_signals)
        total_signals = bullish_signals + bearish_signals

        strength = agreements / total_signals if total_signals > 0 else 0.0

        # Определяем направление
        if bullish_signals > bearish_signals:
            direction_num = 1.0
        elif bearish_signals > bullish_signals:
            direction_num = -1.0
        else:
            direction_num = 0.0

        return (strength, direction_num, agreements, conflicts)
