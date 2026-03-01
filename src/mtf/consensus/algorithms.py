"""
Алгоритмы для Consensus модуля
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np

from .config import get_consensus_config
from .models import (
    ConsensusConfig,
    ConsensusResult,
    ConsensusType,
)

logger = logging.getLogger(__name__)


class WeightCalculator:
    """Калькулятор весов для агрегации"""

    def __init__(self, config: ConsensusConfig | None = None):
        self.config = config or get_consensus_config()

    def calculate_timeframe_weights(self, timeframes: list[str]) -> dict[str, float]:
        """Расчет весов таймфреймов"""
        weights = {}
        total_weight = 0.0

        for tf in timeframes:
            weight = self.config.get_timeframe_weight(tf)
            weights[tf] = weight
            total_weight += weight

        # Нормализация весов
        if total_weight > 0:
            for tf in weights:
                weights[tf] /= total_weight

        return weights

    def calculate_confidence_weights(self, confidences: list[float]) -> list[float]:
        """Расчет весов на основе уверенности"""
        if not confidences:
            return []

        # Применяем confidence boost если включен
        if self.config.enable_confidence_boost:
            boosted_confidences = [
                min(1.0, conf * self.config.confidence_boost_factor)
                for conf in confidences
            ]
        else:
            boosted_confidences = confidences

        # Нормализация
        total_confidence = sum(boosted_confidences)
        if total_confidence > 0:
            return [conf / total_confidence for conf in boosted_confidences]
        return [1.0 / len(confidences)] * len(confidences)

    def calculate_adaptive_weights(
        self,
        context_scores: list[float],
        triggers_scores: list[float],
        confidences: list[float],
    ) -> tuple[float, float]:
        """Адаптивный расчет весов context/triggers"""
        if not context_scores or not triggers_scores:
            return self.config.context_weight, self.config.triggers_weight

        # Средняя уверенность для каждого типа данных
        avg_context_confidence = (
            np.mean(confidences[: len(context_scores)]) if context_scores else 0.0
        )
        avg_triggers_confidence = (
            np.mean(confidences[len(context_scores) :])
            if len(confidences) > len(context_scores)
            else 0.0
        )

        # Адаптивные веса на основе уверенности
        total_confidence = avg_context_confidence + avg_triggers_confidence
        if total_confidence > 0:
            adaptive_context_weight = avg_context_confidence / total_confidence
            adaptive_triggers_weight = avg_triggers_confidence / total_confidence
        else:
            adaptive_context_weight = self.config.context_weight
            adaptive_triggers_weight = self.config.triggers_weight

        # Смешивание с базовыми весами
        context_weight = (
            0.7 * self.config.context_weight + 0.3 * adaptive_context_weight
        )
        triggers_weight = (
            0.7 * self.config.triggers_weight + 0.3 * adaptive_triggers_weight
        )

        # Нормализация
        total_weight = context_weight + triggers_weight
        if total_weight > 0:
            context_weight /= total_weight
            triggers_weight /= total_weight

        return context_weight, triggers_weight


class ConsensusAggregator:
    """Агрегатор для построения консенсуса"""

    def __init__(self, config: ConsensusConfig | None = None):
        self.config = config or get_consensus_config()
        self.weight_calculator = WeightCalculator(config)

    def aggregate_timeframes(
        self, timeframe_data: dict[str, dict[str, float]], timeframes: list[str]
    ) -> dict[str, float]:
        """Агрегация данных по таймфреймам"""
        if not timeframe_data or not timeframes:
            return {}

        # Получаем веса таймфреймов
        tf_weights = self.weight_calculator.calculate_timeframe_weights(timeframes)

        aggregated = {}

        # Агрегируем каждый тип данных
        for data_type in ["context_score", "triggers_score", "confidence"]:
            if data_type in timeframe_data.get(timeframes[0], {}):
                weighted_sum = 0.0
                total_weight = 0.0

                for tf in timeframes:
                    if tf in timeframe_data and data_type in timeframe_data[tf]:
                        weight = tf_weights.get(tf, 0.0)
                        value = timeframe_data[tf][data_type]
                        weighted_sum += value * weight
                        total_weight += weight

                if total_weight > 0:
                    aggregated[data_type] = weighted_sum / total_weight
                else:
                    aggregated[data_type] = 0.0

        return aggregated

    def detect_conflicts(
        self, context_score: float, triggers_score: float
    ) -> tuple[bool, float]:
        """Обнаружение конфликтов между context и triggers"""
        score_diff = abs(context_score - triggers_score)
        is_conflict = score_diff > self.config.conflict_threshold

        conflict_strength = min(1.0, score_diff / self.config.conflict_threshold)

        return is_conflict, conflict_strength

    def calculate_consensus_score(
        self,
        context_score: float,
        triggers_score: float,
        context_confidence: float,
        triggers_confidence: float,
    ) -> tuple[float, float, float]:
        """Расчет итогового счета консенсуса"""

        # Адаптивные веса
        context_weight, triggers_weight = (
            self.weight_calculator.calculate_adaptive_weights(
                [context_score],
                [triggers_score],
                [context_confidence, triggers_confidence],
            )
        )

        # Взвешенная агрегация
        final_score = context_score * context_weight + triggers_score * triggers_weight

        # Общая уверенность
        total_confidence = (
            context_confidence * context_weight + triggers_confidence * triggers_weight
        )

        # Обнаружение конфликтов
        is_conflict, conflict_strength = self.detect_conflicts(
            context_score, triggers_score
        )

        # Корректировка уверенности при конфликтах
        if is_conflict:
            total_confidence *= 1.0 - conflict_strength * 0.3

        return final_score, total_confidence, context_weight

    def determine_consensus_type(
        self, score: float, confidence: float, is_conflict: bool
    ) -> ConsensusType:
        """Определение типа консенсуса"""

        if is_conflict or confidence < self.config.min_confidence_for_consensus:
            return ConsensusType.CONFLICTED

        return self.config.get_consensus_type(score)

    def generate_evidence(
        self,
        context_score: float,
        triggers_score: float,
        consensus_type: ConsensusType,
        confidence: float,
    ) -> tuple[list[str], list[str]]:
        """Генерация поддерживающих и конфликтующих факторов"""

        supporting = []
        conflicting = []

        # Анализ направления
        if consensus_type in [ConsensusType.BULLISH, ConsensusType.STRONG_BULLISH]:
            if context_score > 0:
                supporting.append("Positive context trend")
            if triggers_score > 0:
                supporting.append("Bullish trigger signals")
        elif consensus_type in [ConsensusType.BEARISH, ConsensusType.STRONG_BEARISH]:
            if context_score < 0:
                supporting.append("Negative context trend")
            if triggers_score < 0:
                supporting.append("Bearish trigger signals")

        # Анализ уверенности
        if confidence >= self.config.high_confidence:
            supporting.append("High confidence signals")
        elif confidence < self.config.low_confidence:
            conflicting.append("Low confidence signals")

        # Анализ конфликтов
        score_diff = abs(context_score - triggers_score)
        if score_diff > self.config.conflict_threshold:
            conflicting.append("Conflicting context and triggers signals")

        # Анализ силы сигнала
        avg_score = (context_score + triggers_score) / 2
        if abs(avg_score) >= self.config.strong_bullish_threshold or abs(
            avg_score
        ) >= abs(self.config.strong_bearish_threshold):
            supporting.append("Strong signal strength")
        elif abs(avg_score) < 0.1:
            conflicting.append("Weak signal strength")

        return supporting, conflicting

    def build_consensus(
        self,
        symbol: str,
        timeframes: list[str],
        context_data: dict[str, Any],
        triggers_data: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> ConsensusResult:
        """Построение консенсуса"""

        if timestamp is None:
            timestamp = datetime.now()

        # Агрегация по таймфреймам
        timeframe_breakdown = {}
        aggregated_scores = {
            "context_score": 0.0,
            "triggers_score": 0.0,
            "confidence": 0.0,
        }

        if self.config.enable_timeframe_aggregation and timeframes:
            # Собираем данные по таймфреймам
            tf_data = {}
            for tf in timeframes:
                tf_data[tf] = {
                    "context_score": context_data.get(f"{tf}_context_score", 0.0),
                    "triggers_score": triggers_data.get(f"{tf}_triggers_score", 0.0),
                    "confidence": (
                        context_data.get(f"{tf}_confidence", 0.0)
                        + triggers_data.get(f"{tf}_confidence", 0.0)
                    )
                    / 2,
                }
                timeframe_breakdown[tf] = tf_data[tf].copy()

            # Агрегируем
            aggregated_scores = self.aggregate_timeframes(tf_data, timeframes)
        else:
            # Прямое использование данных
            aggregated_scores = {
                "context_score": context_data.get("context_score", 0.0),
                "triggers_score": triggers_data.get("triggers_score", 0.0),
                "confidence": (
                    context_data.get("confidence", 0.0)
                    + triggers_data.get("confidence", 0.0)
                )
                / 2,
            }

        # Расчет консенсуса
        final_score, total_confidence, context_weight = self.calculate_consensus_score(
            aggregated_scores["context_score"],
            aggregated_scores["triggers_score"],
            context_data.get("confidence", 0.0),
            triggers_data.get("confidence", 0.0),
        )

        # Обнаружение конфликтов
        is_conflict, conflict_strength = self.detect_conflicts(
            aggregated_scores["context_score"], aggregated_scores["triggers_score"]
        )

        # Определение типа консенсуса
        consensus_type = self.determine_consensus_type(
            final_score, total_confidence, is_conflict
        )
        confidence_level = self.config.get_confidence_level(total_confidence)

        # Генерация доказательств
        supporting_evidence, conflicting_evidence = self.generate_evidence(
            aggregated_scores["context_score"],
            aggregated_scores["triggers_score"],
            consensus_type,
            total_confidence,
        )

        # Генерация предупреждений
        warnings = []
        if is_conflict:
            warnings.append("Conflicting signals detected")
        if total_confidence < self.config.min_confidence_for_consensus:
            warnings.append("Low confidence consensus")
        if consensus_type == ConsensusType.CONFLICTED:
            warnings.append("Consensus type is conflicted")

        return ConsensusResult(
            symbol=symbol,
            timestamp=timestamp,
            consensus_type=consensus_type,
            confidence_level=confidence_level,
            final_score=final_score,
            context_weight=context_weight,
            triggers_weight=1.0 - context_weight,
            timeframe_breakdown=timeframe_breakdown,
            supporting_evidence=supporting_evidence,
            conflicting_evidence=conflicting_evidence,
            warnings=warnings,
            is_valid=len(warnings) == 0 or consensus_type != ConsensusType.CONFLICTED,
            metadata={
                "conflict_strength": conflict_strength,
                "aggregated_scores": aggregated_scores,
                "calculation_method": "weighted_aggregation",
            },
        )
