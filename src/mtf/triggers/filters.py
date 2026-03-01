"""
Фильтры для Triggers модуля
"""

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ..logging_config import get_triggers_logger
from .config import TriggersConfig
from .models import (
    MicroFilterResult,
    MicroFilterStatus,
    NoiseFilterResult,
    NoiseFilterType,
)

logger = get_triggers_logger()


class MicroFilter:
    """Микро-фильтр для проверки качества триггеров"""

    def __init__(self, config: TriggersConfig):
        self.config = config

    def apply_filter(
        self,
        features_data: pd.DataFrame,
        probability_components: Any,
        acceleration_analysis: Any,
    ) -> MicroFilterResult:
        """Применение микро-фильтра"""
        try:
            factors = []
            scores = []

            # Проверка каждого фактора
            for factor_name in self.config.micro_filter_factors:
                factor_score = self._check_factor(
                    factor_name,
                    features_data,
                    probability_components,
                    acceleration_analysis,
                )
                factors.append(factor_name)
                scores.append(factor_score)

            # Общий score
            overall_score = np.mean(scores) if scores else 0.0

            # Определение статуса
            if overall_score >= self.config.micro_filter_threshold:
                status = MicroFilterStatus.PASSED
            else:
                status = MicroFilterStatus.FAILED

            # Уверенность
            confidence = min(overall_score * 1.2, 1.0)

            return MicroFilterResult(
                status=status,
                score=overall_score,
                factors=factors,
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"Error applying micro filter: {e}")
            return MicroFilterResult(
                status=MicroFilterStatus.FAILED,
                score=0.0,
                factors=["error"],
                confidence=0.0,
            )

    def _check_factor(
        self,
        factor_name: str,
        features_data: pd.DataFrame,
        probability_components: Any,
        acceleration_analysis: Any,
    ) -> float:
        """Проверка конкретного фактора"""
        try:
            if factor_name == "volume_confirmation":
                return self._check_volume_confirmation(features_data)
            if factor_name == "momentum_consistency":
                return self._check_momentum_consistency(
                    features_data, probability_components
                )
            if factor_name == "volatility_check":
                return self._check_volatility_check(features_data)
            if factor_name == "pattern_confirmation":
                return self._check_pattern_confirmation(features_data)
            logger.warning(f"Unknown micro filter factor: {factor_name}")
            return 0.5

        except Exception as e:
            logger.warning(f"Error checking factor {factor_name}: {e}")
            return 0.0

    def _check_volume_confirmation(self, features_data: pd.DataFrame) -> float:
        """Проверка объемного подтверждения"""
        try:
            if (
                "volume" not in features_data.columns
                or "close" not in features_data.columns
            ):
                return 0.0

            # Анализ объема за последние периоды
            recent_volume = features_data["volume"].tail(5)
            recent_prices = features_data["close"].tail(5)

            if len(recent_volume) < 2 or len(recent_prices) < 2:
                return 0.0

            # Средний объем
            avg_volume = recent_volume.mean()
            current_volume = recent_volume.iloc[-1]

            # Изменение цены
            price_change = (
                recent_prices.iloc[-1] - recent_prices.iloc[-2]
            ) / recent_prices.iloc[-2]

            # Объемное подтверждение
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Score на основе соответствия направления цены и объема
            if abs(price_change) > 0.01:  # Значительное изменение цены
                if (price_change > 0 and volume_ratio > 1.2) or (
                    price_change < 0 and volume_ratio > 1.2
                ):
                    return 0.9  # Сильное подтверждение
                if volume_ratio > 1.0:
                    return 0.6  # Умеренное подтверждение
                return 0.2  # Слабое подтверждение
            return 0.5  # Нейтрально

        except Exception as e:
            logger.warning(f"Error checking volume confirmation: {e}")
            return 0.0

    def _check_momentum_consistency(
        self, features_data: pd.DataFrame, probability_components: Any
    ) -> float:
        """Проверка консистентности momentum"""
        try:
            if (
                "rsi_14" not in features_data.columns
                or "macd" not in features_data.columns
            ):
                return 0.0

            current_rsi = features_data["rsi_14"].iloc[-1]
            current_macd = features_data["macd"].iloc[-1]

            # Определение направления momentum
            rsi_direction = 1 if current_rsi > 50 else -1
            macd_direction = 1 if current_macd > 0 else -1

            # Проверка консистентности
            if rsi_direction == macd_direction:
                # Консистентные сигналы
                strength = abs(current_rsi - 50) / 50 + abs(current_macd) / max(
                    abs(current_macd), 0.1
                )
                return min(strength, 1.0)
            # Противоречивые сигналы
            return 0.2

        except Exception as e:
            logger.warning(f"Error checking momentum consistency: {e}")
            return 0.0

    def _check_volatility_check(self, features_data: pd.DataFrame) -> float:
        """Проверка волатильности"""
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

            # Оптимальная волатильность для триггеров
            if 0.02 <= atr_ratio <= 0.05:
                return 0.9  # Оптимальная волатильность
            if 0.01 <= atr_ratio <= 0.08:
                return 0.6  # Приемлемая волатильность
            return 0.2  # Неоптимальная волатильность

        except Exception as e:
            logger.warning(f"Error checking volatility: {e}")
            return 0.0

    def _check_pattern_confirmation(self, features_data: pd.DataFrame) -> float:
        """Проверка подтверждения паттернов"""
        try:
            if "close" not in features_data.columns or len(features_data) < 10:
                return 0.5

            # Анализ последних цен
            recent_prices = features_data["close"].tail(10)

            # Простой анализ паттернов
            price_trend = (
                recent_prices.iloc[-1] - recent_prices.iloc[0]
            ) / recent_prices.iloc[0]
            price_volatility = recent_prices.std() / recent_prices.mean()

            # Score на основе четкости паттерна
            if abs(price_trend) > 0.03 and price_volatility < 0.02:
                return 0.8  # Четкий тренд
            if abs(price_trend) < 0.01 and price_volatility > 0.03:
                return 0.6  # Боковое движение
            return 0.4  # Неопределенный паттерн

        except Exception as e:
            logger.warning(f"Error checking pattern confirmation: {e}")
            return 0.0


class NoiseFilter:
    """Фильтр шума для устранения ложных сигналов"""

    def __init__(self, config: TriggersConfig):
        self.config = config

    def apply_filters(
        self, features_data: pd.DataFrame, trigger_data: Any
    ) -> list[NoiseFilterResult]:
        """Применение всех фильтров шума"""
        results = []

        try:
            # Cluster confirmation filter
            cluster_result = self._apply_cluster_confirmation_filter(
                features_data, trigger_data
            )
            results.append(cluster_result)

            # Volume filter
            volume_result = self._apply_volume_filter(features_data, trigger_data)
            results.append(volume_result)

            # Volatility filter
            volatility_result = self._apply_volatility_filter(
                features_data, trigger_data
            )
            results.append(volatility_result)

            # Time filter
            time_result = self._apply_time_filter(features_data, trigger_data)
            results.append(time_result)

        except Exception as e:
            logger.error(f"Error applying noise filters: {e}")

        return results

    def _apply_cluster_confirmation_filter(
        self, features_data: pd.DataFrame, trigger_data: Any
    ) -> NoiseFilterResult:
        """Применение фильтра кластерного подтверждения"""
        try:
            if (
                "close" not in features_data.columns
                or len(features_data) < self.config.cluster_confirmation_periods
            ):
                return NoiseFilterResult(
                    filter_type=NoiseFilterType.CLUSTER_CONFIRMATION,
                    passed=False,
                    score=0.0,
                    effectiveness=0.0,
                    metadata={"error": "insufficient_data"},
                )

            # Анализ последних периодов
            recent_prices = features_data["close"].tail(
                self.config.cluster_confirmation_periods
            )
            price_changes = recent_prices.pct_change().dropna()

            # Подсчет однонаправленных изменений
            positive_changes = (price_changes > 0).sum()
            negative_changes = (price_changes < 0).sum()
            total_changes = len(price_changes)

            # Определение доминирующего направления
            if positive_changes > negative_changes:
                dominant_direction = 1
                consistency_ratio = positive_changes / total_changes
            elif negative_changes > positive_changes:
                dominant_direction = -1
                consistency_ratio = negative_changes / total_changes
            else:
                dominant_direction = 0
                consistency_ratio = 0.5

            # Проверка соответствия с триггером
            trigger_direction = 1 if trigger_data.p_up > trigger_data.p_down else -1

            # Score
            if dominant_direction == trigger_direction:
                score = consistency_ratio
                passed = consistency_ratio >= 0.6
            else:
                score = 1.0 - consistency_ratio
                passed = False

            effectiveness = min(consistency_ratio * 1.5, 1.0)

            return NoiseFilterResult(
                filter_type=NoiseFilterType.CLUSTER_CONFIRMATION,
                passed=passed,
                score=score,
                effectiveness=effectiveness,
                metadata={
                    "positive_changes": positive_changes,
                    "negative_changes": negative_changes,
                    "consistency_ratio": consistency_ratio,
                    "trigger_direction": trigger_direction,
                },
            )

        except Exception as e:
            logger.warning(f"Error applying cluster confirmation filter: {e}")
            return NoiseFilterResult(
                filter_type=NoiseFilterType.CLUSTER_CONFIRMATION,
                passed=False,
                score=0.0,
                effectiveness=0.0,
                metadata={"error": str(e)},
            )

    def _apply_volume_filter(
        self, features_data: pd.DataFrame, trigger_data: Any
    ) -> NoiseFilterResult:
        """Применение объемного фильтра"""
        try:
            if "volume" not in features_data.columns:
                return NoiseFilterResult(
                    filter_type=NoiseFilterType.VOLUME_FILTER,
                    passed=True,  # Пропускаем если нет данных об объеме
                    score=0.5,
                    effectiveness=0.0,
                    metadata={"error": "no_volume_data"},
                )

            # Анализ объема
            recent_volume = features_data["volume"].tail(10)
            avg_volume = recent_volume.mean()
            current_volume = recent_volume.iloc[-1]

            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Проверка на объемные всплески
            if volume_ratio >= self.config.volume_spike_threshold:
                # Высокий объем - хороший сигнал
                score = min(volume_ratio / self.config.volume_spike_threshold, 1.0)
                passed = True
                effectiveness = 0.8
            elif volume_ratio >= 1.0:
                # Нормальный объем
                score = 0.6
                passed = True
                effectiveness = 0.5
            else:
                # Низкий объем - слабый сигнал
                score = volume_ratio
                passed = False
                effectiveness = 0.2

            return NoiseFilterResult(
                filter_type=NoiseFilterType.VOLUME_FILTER,
                passed=passed,
                score=score,
                effectiveness=effectiveness,
                metadata={
                    "volume_ratio": volume_ratio,
                    "current_volume": current_volume,
                    "avg_volume": avg_volume,
                },
            )

        except Exception as e:
            logger.warning(f"Error applying volume filter: {e}")
            return NoiseFilterResult(
                filter_type=NoiseFilterType.VOLUME_FILTER,
                passed=False,
                score=0.0,
                effectiveness=0.0,
                metadata={"error": str(e)},
            )

    def _apply_volatility_filter(
        self, features_data: pd.DataFrame, trigger_data: Any
    ) -> NoiseFilterResult:
        """Применение фильтра волатильности"""
        try:
            if (
                "atr" not in features_data.columns
                or "close" not in features_data.columns
            ):
                return NoiseFilterResult(
                    filter_type=NoiseFilterType.VOLATILITY_FILTER,
                    passed=True,
                    score=0.5,
                    effectiveness=0.0,
                    metadata={"error": "no_volatility_data"},
                )

            current_atr = features_data["atr"].iloc[-1]
            current_price = features_data["close"].iloc[-1]

            atr_ratio = current_atr / current_price if current_price > 0 else 0

            # Оптимальная волатильность для триггеров
            if 0.02 <= atr_ratio <= 0.05:
                score = 0.9
                passed = True
                effectiveness = 0.8
            elif 0.01 <= atr_ratio <= 0.08:
                score = 0.6
                passed = True
                effectiveness = 0.5
            else:
                score = 0.3
                passed = False
                effectiveness = 0.2

            return NoiseFilterResult(
                filter_type=NoiseFilterType.VOLATILITY_FILTER,
                passed=passed,
                score=score,
                effectiveness=effectiveness,
                metadata={
                    "atr_ratio": atr_ratio,
                    "current_atr": current_atr,
                    "current_price": current_price,
                },
            )

        except Exception as e:
            logger.warning(f"Error applying volatility filter: {e}")
            return NoiseFilterResult(
                filter_type=NoiseFilterType.VOLATILITY_FILTER,
                passed=False,
                score=0.0,
                effectiveness=0.0,
                metadata={"error": str(e)},
            )

    def _apply_time_filter(
        self, features_data: pd.DataFrame, trigger_data: Any
    ) -> NoiseFilterResult:
        """Применение временного фильтра"""
        try:
            # Проверка времени последнего обновления данных
            if hasattr(features_data.index, "max"):
                last_update = features_data.index.max()
                if isinstance(last_update, pd.Timestamp):
                    time_diff = datetime.now() - last_update.to_pydatetime()
                    age_hours = time_diff.total_seconds() / 3600

                    if age_hours <= 1:
                        score = 0.9
                        passed = True
                        effectiveness = 0.8
                    elif age_hours <= 4:
                        score = 0.7
                        passed = True
                        effectiveness = 0.6
                    elif age_hours <= 12:
                        score = 0.5
                        passed = True
                        effectiveness = 0.4
                    else:
                        score = 0.2
                        passed = False
                        effectiveness = 0.1
                else:
                    score = 0.5
                    passed = True
                    effectiveness = 0.3
            else:
                score = 0.5
                passed = True
                effectiveness = 0.3

            return NoiseFilterResult(
                filter_type=NoiseFilterType.TIME_FILTER,
                passed=passed,
                score=score,
                effectiveness=effectiveness,
                metadata={
                    "data_age_hours": age_hours if "age_hours" in locals() else None
                },
            )

        except Exception as e:
            logger.warning(f"Error applying time filter: {e}")
            return NoiseFilterResult(
                filter_type=NoiseFilterType.TIME_FILTER,
                passed=True,  # Пропускаем по умолчанию
                score=0.5,
                effectiveness=0.0,
                metadata={"error": str(e)},
            )

    def calculate_overall_effectiveness(
        self, filter_results: list[NoiseFilterResult]
    ) -> float:
        """Расчет общей эффективности фильтров"""
        if not filter_results:
            return 0.0

        # Взвешенная средняя эффективности
        weights = {
            NoiseFilterType.CLUSTER_CONFIRMATION: 0.4,
            NoiseFilterType.VOLUME_FILTER: 0.3,
            NoiseFilterType.VOLATILITY_FILTER: 0.2,
            NoiseFilterType.TIME_FILTER: 0.1,
        }

        total_weighted_effectiveness = 0.0
        total_weight = 0.0

        for result in filter_results:
            weight = weights.get(result.filter_type, 0.1)
            total_weighted_effectiveness += result.effectiveness * weight
            total_weight += weight

        return total_weighted_effectiveness / total_weight if total_weight > 0 else 0.0
