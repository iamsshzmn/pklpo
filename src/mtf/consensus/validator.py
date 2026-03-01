"""
Валидатор для Consensus модуля
"""

import logging
from datetime import datetime
from typing import Any

from .models import (
    ConsensusConfig,
    ConsensusRequest,
    ConsensusResult,
    ValidationResult,
    ValidationStatus,
)

logger = logging.getLogger(__name__)


class ConsensusValidator:
    """Валидатор для консенсуса"""

    def __init__(self, config: ConsensusConfig):
        self.config = config

    def validate_request(self, request: ConsensusRequest) -> ValidationResult:
        """Валидация запроса на консенсус"""
        errors = []
        warnings = []

        # Проверка символа
        if not request.symbol or not isinstance(request.symbol, str):
            errors.append("Symbol must be a non-empty string")

        # Проверка таймфреймов
        if not request.timeframes or not isinstance(request.timeframes, list):
            errors.append("Timeframes must be a non-empty list")
        elif len(request.timeframes) < self.config.min_data_points:
            warnings.append(
                f"Too few timeframes: {len(request.timeframes)} < {self.config.min_data_points}"
            )

        # Проверка данных контекста
        if request.context_data is None:
            warnings.append("No context data provided")
        elif not isinstance(request.context_data, dict):
            errors.append("Context data must be a dictionary")

        # Проверка данных триггеров
        if request.triggers_data is None:
            warnings.append("No triggers data provided")
        elif not isinstance(request.triggers_data, dict):
            errors.append("Triggers data must be a dictionary")

        # Проверка временной метки
        if request.timestamp is None:
            warnings.append("No timestamp provided, using current time")
        elif isinstance(request.timestamp, datetime):
            age_hours = (datetime.now() - request.timestamp).total_seconds() / 3600
            if age_hours > self.config.max_age_hours:
                warnings.append(
                    f"Data is {age_hours:.1f} hours old, max allowed: {self.config.max_age_hours}"
                )

        # Проверка кастомных весов
        if request.custom_weights is not None:
            if not isinstance(request.custom_weights, dict):
                errors.append("Custom weights must be a dictionary")
            else:
                for key, value in request.custom_weights.items():
                    if not isinstance(value, int | float) or value < 0:
                        errors.append(
                            f"Custom weight for '{key}' must be a non-negative number"
                        )

        # Определение статуса
        if errors:
            status = ValidationStatus.INVALID
        elif warnings:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID

        return ValidationResult(
            status=status,
            message=f"Validation {'failed' if errors else 'passed with warnings' if warnings else 'passed'}",
            details={
                "errors": errors,
                "warnings": warnings,
                "symbol": request.symbol,
                "timeframes_count": (
                    len(request.timeframes) if request.timeframes else 0
                ),
            },
        )

    def validate_result(self, result: ConsensusResult) -> ValidationResult:
        """Валидация результата консенсуса"""
        errors = []
        warnings = []

        # Проверка символа
        if not result.symbol or not isinstance(result.symbol, str):
            errors.append("Result symbol must be a non-empty string")

        # Проверка временной метки
        if not isinstance(result.timestamp, datetime):
            errors.append("Result timestamp must be a datetime object")

        # Проверка финального счета
        if not isinstance(result.final_score, int | float):
            errors.append("Final score must be a number")
        elif abs(result.final_score) > 2.0:
            warnings.append(f"Final score is unusually high: {result.final_score}")

        # Проверка весов
        if (
            not isinstance(result.context_weight, int | float)
            or result.context_weight < 0
            or result.context_weight > 1
        ):
            errors.append("Context weight must be between 0 and 1")

        if (
            not isinstance(result.triggers_weight, int | float)
            or result.triggers_weight < 0
            or result.triggers_weight > 1
        ):
            errors.append("Triggers weight must be between 0 and 1")

        # Проверка суммы весов
        weight_sum = result.context_weight + result.triggers_weight
        if abs(weight_sum - 1.0) > 0.01:
            warnings.append(f"Weights don't sum to 1.0: {weight_sum}")

        # Проверка типа консенсуса
        if result.consensus_type is None:
            errors.append("Consensus type must be specified")

        # Проверка уровня уверенности
        if result.confidence_level is None:
            errors.append("Confidence level must be specified")

        # Проверка валидности
        if not isinstance(result.is_valid, bool):
            errors.append("Is valid must be a boolean")

        # Проверка предупреждений
        if result.warnings and not isinstance(result.warnings, list):
            errors.append("Warnings must be a list")

        # Проверка доказательств
        if not isinstance(result.supporting_evidence, list):
            errors.append("Supporting evidence must be a list")

        if not isinstance(result.conflicting_evidence, list):
            errors.append("Conflicting evidence must be a list")

        # Проверка разбивки по таймфреймам
        if not isinstance(result.timeframe_breakdown, dict):
            errors.append("Timeframe breakdown must be a dictionary")

        # Определение статуса
        if errors:
            status = ValidationStatus.INVALID
        elif warnings or result.warnings:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID

        return ValidationResult(
            status=status,
            message=f"Result validation {'failed' if errors else 'passed with warnings' if warnings else 'passed'}",
            details={
                "errors": errors,
                "warnings": warnings,
                "symbol": result.symbol,
                "consensus_type": (
                    result.consensus_type.value if result.consensus_type else None
                ),
                "confidence_level": (
                    result.confidence_level.value if result.confidence_level else None
                ),
                "final_score": result.final_score,
                "is_valid": result.is_valid,
            },
        )

    def validate_data_quality(
        self, context_data: dict[str, Any], triggers_data: dict[str, Any]
    ) -> ValidationResult:
        """Валидация качества данных"""
        errors = []
        warnings = []

        # Проверка контекстных данных
        if context_data:
            if "context_score" not in context_data:
                warnings.append("No context_score in context data")
            elif not isinstance(context_data["context_score"], int | float):
                errors.append("Context score must be a number")

            if "confidence" not in context_data:
                warnings.append("No confidence in context data")
            elif (
                not isinstance(context_data["confidence"], int | float)
                or context_data["confidence"] < 0
                or context_data["confidence"] > 1
            ):
                errors.append("Context confidence must be between 0 and 1")

        # Проверка данных триггеров
        if triggers_data:
            if "triggers_score" not in triggers_data:
                warnings.append("No triggers_score in triggers data")
            elif not isinstance(triggers_data["triggers_score"], int | float):
                errors.append("Triggers score must be a number")

            if "confidence" not in triggers_data:
                warnings.append("No confidence in triggers data")
            elif (
                not isinstance(triggers_data["confidence"], int | float)
                or triggers_data["confidence"] < 0
                or triggers_data["confidence"] > 1
            ):
                errors.append("Triggers confidence must be between 0 and 1")

        # Проверка согласованности данных
        if context_data and triggers_data:
            context_score = context_data.get("context_score", 0)
            triggers_score = triggers_data.get("triggers_score", 0)

            score_diff = abs(context_score - triggers_score)
            if score_diff > self.config.conflict_threshold:
                warnings.append(f"Large score difference detected: {score_diff:.3f}")

        # Определение статуса
        if errors:
            status = ValidationStatus.INVALID
        elif warnings:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID

        return ValidationResult(
            status=status,
            message=f"Data quality validation {'failed' if errors else 'passed with warnings' if warnings else 'passed'}",
            details={
                "errors": errors,
                "warnings": warnings,
                "context_data_keys": list(context_data.keys()) if context_data else [],
                "triggers_data_keys": (
                    list(triggers_data.keys()) if triggers_data else []
                ),
            },
        )
