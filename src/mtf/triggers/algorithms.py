"""
Алгоритмы для построения триггеров
"""

from typing import Any

import numpy as np
import pandas as pd

from ..logging_config import get_triggers_logger
from .config import TriggersConfig
from .models import (
    AccelerationAnalysis,
    AccelerationType,
    ProbabilityComponents,
)

logger = get_triggers_logger()


class ProbabilityCalculator:
    """Калькулятор вероятностей разворота"""

    def __init__(self, config: TriggersConfig):
        self.config = config

    def calculate_probabilities(
        self, features_data: pd.DataFrame, context_data: dict[str, Any] | None = None
    ) -> ProbabilityComponents:
        """Расчет вероятностей разворота"""
        try:
            # Компоненты вероятности
            momentum_factor = self._calculate_momentum_factor(features_data)
            volume_factor = self._calculate_volume_factor(features_data)
            volatility_factor = self._calculate_volatility_factor(features_data)
            support_resistance_factor = self._calculate_support_resistance_factor(
                features_data
            )
            pattern_factor = self._calculate_pattern_factor(features_data)

            # Расчет финальных вероятностей
            final_p_up = self._calculate_final_probability(
                momentum_factor,
                volume_factor,
                volatility_factor,
                support_resistance_factor,
                pattern_factor,
                direction="up",
            )

            final_p_down = self._calculate_final_probability(
                momentum_factor,
                volume_factor,
                volatility_factor,
                support_resistance_factor,
                pattern_factor,
                direction="down",
            )

            return ProbabilityComponents(
                momentum_factor=momentum_factor,
                volume_factor=volume_factor,
                volatility_factor=volatility_factor,
                support_resistance_factor=support_resistance_factor,
                pattern_factor=pattern_factor,
                final_p_up=final_p_up,
                final_p_down=final_p_down,
            )

        except Exception as e:
            logger.error(f"Error calculating probabilities: {e}")
            return ProbabilityComponents(
                momentum_factor=0.0,
                volume_factor=0.0,
                volatility_factor=0.0,
                support_resistance_factor=0.0,
                pattern_factor=0.0,
                final_p_up=0.5,
                final_p_down=0.5,
            )

    def _calculate_momentum_factor(self, features_data: pd.DataFrame) -> float:
        """Расчет фактора momentum"""
        try:
            if (
                "rsi_14" not in features_data.columns
                or "macd" not in features_data.columns
            ):
                return 0.0

            current_rsi = features_data["rsi_14"].iloc[-1]
            current_macd = features_data["macd"].iloc[-1]

            # RSI momentum
            rsi_momentum = 0.0
            if current_rsi <= 30:
                rsi_momentum = 0.8  # Сильный бычий momentum
            elif current_rsi >= 70:
                rsi_momentum = -0.8  # Сильный медвежий momentum
            elif current_rsi < 50:
                rsi_momentum = 0.3  # Слабый бычий momentum
            else:
                rsi_momentum = -0.3  # Слабый медвежий momentum

            # MACD momentum
            macd_momentum = 0.0
            if "macd_signal" in features_data.columns:
                current_signal = features_data["macd_signal"].iloc[-1]
                macd_momentum = 0.6 if current_macd > current_signal else -0.6
            else:
                macd_momentum = np.tanh(current_macd * 10)

            # Комбинированный momentum
            combined_momentum = (rsi_momentum + macd_momentum) / 2

            # Нормализация в диапазон [0, 1]
            return (combined_momentum + 1) / 2

        except Exception as e:
            logger.warning(f"Error calculating momentum factor: {e}")
            return 0.5

    def _calculate_volume_factor(self, features_data: pd.DataFrame) -> float:
        """Расчет фактора объема"""
        try:
            if (
                "volume" not in features_data.columns
                or "close" not in features_data.columns
            ):
                return 0.5

            # Анализ объема за последние периоды
            recent_volume = features_data["volume"].tail(10)
            recent_prices = features_data["close"].tail(10)

            if len(recent_volume) < 2 or len(recent_prices) < 2:
                return 0.5

            # Средний объем
            avg_volume = recent_volume.mean()
            current_volume = recent_volume.iloc[-1]

            # Изменение цены
            price_change = (
                recent_prices.iloc[-1] - recent_prices.iloc[-2]
            ) / recent_prices.iloc[-2]

            # Объемное подтверждение
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Расчет фактора
            if price_change > 0 and volume_ratio > 1.2:
                return 0.8  # Сильное бычье подтверждение
            if price_change < 0 and volume_ratio > 1.2:
                return 0.2  # Сильное медвежье подтверждение
            if volume_ratio < 0.8:
                return 0.3  # Слабое подтверждение
            return 0.5  # Нейтральное подтверждение

        except Exception as e:
            logger.warning(f"Error calculating volume factor: {e}")
            return 0.5

    def _calculate_volatility_factor(self, features_data: pd.DataFrame) -> float:
        """Расчет фактора волатильности"""
        try:
            if (
                "atr" not in features_data.columns
                or "close" not in features_data.columns
            ):
                return 0.5

            current_atr = features_data["atr"].iloc[-1]
            current_price = features_data["close"].iloc[-1]

            # ATR как процент от цены
            atr_ratio = current_atr / current_price if current_price > 0 else 0

            # Анализ волатильности
            if atr_ratio > 0.05:  # Высокая волатильность
                return 0.3  # Снижает уверенность
            if atr_ratio > 0.03:  # Средняя волатильность
                return 0.5  # Нейтральная
            # Низкая волатильность
            return 0.7  # Повышает уверенность

        except Exception as e:
            logger.warning(f"Error calculating volatility factor: {e}")
            return 0.5

    def _calculate_support_resistance_factor(
        self, features_data: pd.DataFrame
    ) -> float:
        """Расчет фактора поддержки/сопротивления"""
        try:
            if (
                "close" not in features_data.columns
                or "high" not in features_data.columns
                or "low" not in features_data.columns
            ):
                return 0.5

            current_price = features_data["close"].iloc[-1]
            recent_highs = features_data["high"].tail(20)
            recent_lows = features_data["low"].tail(20)

            if len(recent_highs) < 10 or len(recent_lows) < 10:
                return 0.5

            # Уровни поддержки и сопротивления
            resistance_level = recent_highs.max()
            support_level = recent_lows.min()

            # Расстояние до уровней
            resistance_distance = (resistance_level - current_price) / current_price
            support_distance = (current_price - support_level) / current_price

            # Фактор близости к уровням
            if resistance_distance < 0.02:  # Близко к сопротивлению
                return 0.2  # Высокая вероятность разворота вниз
            if support_distance < 0.02:  # Близко к поддержке
                return 0.8  # Высокая вероятность разворота вверх
            return 0.5  # Нейтрально

        except Exception as e:
            logger.warning(f"Error calculating support/resistance factor: {e}")
            return 0.5

    def _calculate_pattern_factor(self, features_data: pd.DataFrame) -> float:
        """Расчет фактора паттернов"""
        try:
            if "close" not in features_data.columns or len(features_data) < 10:
                return 0.5

            # Простой анализ паттернов
            recent_prices = features_data["close"].tail(10)

            # Тренд
            price_trend = (
                recent_prices.iloc[-1] - recent_prices.iloc[0]
            ) / recent_prices.iloc[0]

            # Волатильность
            price_volatility = recent_prices.std() / recent_prices.mean()

            # Комбинированный фактор
            if abs(price_trend) > 0.05 and price_volatility < 0.02:
                # Сильный тренд с низкой волатильностью
                return 0.8 if price_trend > 0 else 0.2
            if abs(price_trend) < 0.02 and price_volatility > 0.03:
                # Боковое движение с высокой волатильностью
                return 0.3
            return 0.5

        except Exception as e:
            logger.warning(f"Error calculating pattern factor: {e}")
            return 0.5

    def _calculate_final_probability(
        self,
        momentum: float,
        volume: float,
        volatility: float,
        support_resistance: float,
        pattern: float,
        direction: str,
    ) -> float:
        """Расчет финальной вероятности"""
        # Взвешенная сумма компонентов
        weighted_sum = (
            momentum * self.config.momentum_weight
            + volume * self.config.volume_weight
            + volatility * self.config.volatility_weight
            + support_resistance * self.config.support_resistance_weight
            + pattern * self.config.pattern_weight
        )

        # Корректировка для направления
        if direction == "up":
            return np.clip(weighted_sum, 0.0, 1.0)
        # down
        return np.clip(1.0 - weighted_sum, 0.0, 1.0)


class AccelerationAnalyzer:
    """Анализатор ускорения"""

    def __init__(self, config: TriggersConfig):
        self.config = config

    def analyze_acceleration(self, features_data: pd.DataFrame) -> AccelerationAnalysis:
        """Анализ ускорения"""
        try:
            # Расчет ускорения
            acceleration_value = self._calculate_acceleration(features_data)

            # Определение типа ускорения
            if acceleration_value > self.config.acceleration_threshold:
                acceleration_type = AccelerationType.BULLISH
            elif acceleration_value < -self.config.acceleration_threshold:
                acceleration_type = AccelerationType.BEARISH
            else:
                acceleration_type = AccelerationType.NEUTRAL

            # Сила ускорения
            strength = abs(acceleration_value)

            # Длительность ускорения
            duration = self._calculate_acceleration_duration(
                features_data, acceleration_type
            )

            # Уверенность
            confidence = self._calculate_acceleration_confidence(
                features_data, acceleration_type
            )

            # Факторы
            factors = self._identify_acceleration_factors(
                features_data, acceleration_type
            )

            return AccelerationAnalysis(
                acceleration=acceleration_type,
                strength=strength,
                duration=duration,
                confidence=confidence,
                factors=factors,
            )

        except Exception as e:
            logger.error(f"Error analyzing acceleration: {e}")
            return AccelerationAnalysis(
                acceleration=AccelerationType.NEUTRAL,
                strength=0.0,
                duration=0,
                confidence=0.0,
                factors=["error"],
            )

    def _calculate_acceleration(self, features_data: pd.DataFrame) -> float:
        """Расчет значения ускорения"""
        try:
            if "close" not in features_data.columns or len(features_data) < 5:
                return 0.0

            # Расчет скорости изменения цены
            prices = features_data["close"].tail(10)
            price_changes = prices.pct_change().dropna()

            if len(price_changes) < 3:
                return 0.0

            # Ускорение как изменение скорости
            velocity = price_changes.mean()
            acceleration = price_changes.diff().mean()

            # Комбинированный показатель
            combined_acceleration = (velocity + acceleration) / 2

            # Нормализация
            return np.tanh(combined_acceleration * 10)

        except Exception as e:
            logger.warning(f"Error calculating acceleration: {e}")
            return 0.0

    def _calculate_acceleration_duration(
        self, features_data: pd.DataFrame, acceleration_type: AccelerationType
    ) -> int:
        """Расчет длительности ускорения"""
        try:
            if "close" not in features_data.columns or len(features_data) < 5:
                return 0

            # Анализ последних периодов
            recent_prices = features_data["close"].tail(20)
            price_changes = recent_prices.pct_change().dropna()

            duration = 0
            for i in range(len(price_changes) - 1, -1, -1):
                change = price_changes.iloc[i]

                if (
                    (acceleration_type == AccelerationType.BULLISH
                    and change > 0)
                    or (acceleration_type == AccelerationType.BEARISH
                    and change < 0)
                ):
                    duration += 1
                else:
                    break

            return min(duration, len(price_changes))

        except Exception as e:
            logger.warning(f"Error calculating acceleration duration: {e}")
            return 0

    def _calculate_acceleration_confidence(
        self, features_data: pd.DataFrame, acceleration_type: AccelerationType
    ) -> float:
        """Расчет уверенности в ускорении"""
        try:
            # Факторы уверенности
            factors = []

            # Объемное подтверждение
            if "volume" in features_data.columns:
                recent_volume = features_data["volume"].tail(5)
                avg_volume = recent_volume.mean()
                current_volume = recent_volume.iloc[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

                if volume_ratio > 1.2:
                    factors.append(0.2)
                else:
                    factors.append(0.0)

            # Momentum подтверждение
            if "rsi_14" in features_data.columns:
                current_rsi = features_data["rsi_14"].iloc[-1]

                if (
                    (acceleration_type == AccelerationType.BULLISH
                    and current_rsi < 70)
                    or (acceleration_type == AccelerationType.BEARISH
                    and current_rsi > 30)
                ):
                    factors.append(0.2)
                else:
                    factors.append(0.0)

            # Волатильность
            if "atr" in features_data.columns and "close" in features_data.columns:
                current_atr = features_data["atr"].iloc[-1]
                current_price = features_data["close"].iloc[-1]
                atr_ratio = current_atr / current_price if current_price > 0 else 0

                if 0.02 <= atr_ratio <= 0.05:  # Оптимальная волатильность
                    factors.append(0.2)
                else:
                    factors.append(0.1)

            # Базовая уверенность
            base_confidence = 0.4

            return min(base_confidence + sum(factors), 1.0)

        except Exception as e:
            logger.warning(f"Error calculating acceleration confidence: {e}")
            return 0.5

    def _identify_acceleration_factors(
        self, features_data: pd.DataFrame, acceleration_type: AccelerationType
    ) -> list[str]:
        """Идентификация факторов ускорения"""
        factors = []

        try:
            # Объемные факторы
            if "volume" in features_data.columns:
                recent_volume = features_data["volume"].tail(5)
                avg_volume = recent_volume.mean()
                current_volume = recent_volume.iloc[-1]
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

                if volume_ratio > 1.5:
                    factors.append("high_volume")
                elif volume_ratio < 0.7:
                    factors.append("low_volume")

            # Momentum факторы
            if "rsi_14" in features_data.columns:
                current_rsi = features_data["rsi_14"].iloc[-1]

                if current_rsi <= 30:
                    factors.append("oversold")
                elif current_rsi >= 70:
                    factors.append("overbought")

            # MACD факторы
            if (
                "macd" in features_data.columns
                and "macd_signal" in features_data.columns
            ):
                current_macd = features_data["macd"].iloc[-1]
                current_signal = features_data["macd_signal"].iloc[-1]

                if current_macd > current_signal:
                    factors.append("macd_bullish")
                else:
                    factors.append("macd_bearish")

            # Волатильность факторы
            if "atr" in features_data.columns and "close" in features_data.columns:
                current_atr = features_data["atr"].iloc[-1]
                current_price = features_data["close"].iloc[-1]
                atr_ratio = current_atr / current_price if current_price > 0 else 0

                if atr_ratio > 0.05:
                    factors.append("high_volatility")
                elif atr_ratio < 0.02:
                    factors.append("low_volatility")

        except Exception as e:
            logger.warning(f"Error identifying acceleration factors: {e}")
            factors.append("error")

        return factors
