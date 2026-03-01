"""
Валидатор для Context Builder
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import ContextConfig
from .models import (
    ContextData,
    ContextRequest,
    ContextResult,
    ReasonCode,
    RegimeType,
    ValidationResult,
    ValidationStatus,
)

logger = logging.getLogger(__name__)


class ContextValidator:
    """Валидатор контекста"""

    def __init__(self, config: ContextConfig):
        self.config = config

    def validate_request(self, request: ContextRequest) -> ValidationResult:
        """Валидация запроса на построение контекста"""
        errors = []
        warnings = []

        try:
            # Валидация символа
            if not request.symbol or not isinstance(request.symbol, str):
                errors.append("Symbol must be a non-empty string")

            # Валидация таймфреймов
            if not request.timeframes or not isinstance(request.timeframes, list):
                errors.append("Timeframes must be a non-empty list")
            else:
                for tf in request.timeframes:
                    if not isinstance(tf, str) or not tf:
                        errors.append(f"Invalid timeframe: {tf}")

            # Валидация временной метки
            if request.timestamp and not isinstance(request.timestamp, datetime):
                errors.append("Timestamp must be a datetime object")

            # Валидация данных features
            if request.features_data:
                for tf, data in request.features_data.items():
                    if not isinstance(data, pd.DataFrame):
                        errors.append(f"Features data for {tf} must be a DataFrame")
                    elif data.empty:
                        warnings.append(f"Features data for {tf} is empty")
                    elif len(data) < self.config.min_data_points:
                        warnings.append(
                            f"Features data for {tf} has insufficient data points: {len(data)} < {self.config.min_data_points}"
                        )

            # Определение статуса
            if errors:
                status = ValidationStatus.ERROR
            elif warnings:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID

            return ValidationResult(
                status=status,
                message=f"Request validation: {status.value}",
                errors=errors,
                warnings=warnings,
                metadata={
                    "symbol": request.symbol,
                    "timeframes_count": (
                        len(request.timeframes) if request.timeframes else 0
                    ),
                    "has_features_data": bool(request.features_data),
                    "has_market_meta_data": bool(request.market_meta_data),
                },
            )

        except Exception as e:
            logger.error(f"Error validating request: {e}")
            return ValidationResult(
                status=ValidationStatus.ERROR,
                message=f"Validation error: {e!s}",
                errors=[str(e)],
                warnings=[],
                metadata={},
            )

    def validate_features_data(
        self, features_data: pd.DataFrame, timeframe: str
    ) -> ValidationResult:
        """Валидация данных индикаторов"""
        errors = []
        warnings = []

        try:
            # Проверка на пустые данные
            if features_data.empty:
                errors.append("Features data is empty")
                return ValidationResult(
                    status=ValidationStatus.ERROR,
                    message="Empty features data",
                    errors=errors,
                    warnings=warnings,
                    metadata={"timeframe": timeframe},
                )

            # Проверка минимального количества данных
            if len(features_data) < self.config.min_data_points:
                errors.append(
                    f"Insufficient data points: {len(features_data)} < {self.config.min_data_points}"
                )

            # Проверка обязательных колонок
            required_columns = ["close", "volume"]
            missing_columns = [
                col for col in required_columns if col not in features_data.columns
            ]
            if missing_columns:
                errors.append(f"Missing required columns: {missing_columns}")

            # Проверка на NaN значения
            nan_columns = features_data.columns[features_data.isnull().any()].tolist()
            if nan_columns:
                warnings.append(f"Columns with NaN values: {nan_columns}")

            # Проверка на бесконечные значения
            inf_columns = []
            for col in features_data.select_dtypes(include=[np.number]).columns:
                if np.isinf(features_data[col]).any():
                    inf_columns.append(col)
            if inf_columns:
                errors.append(f"Columns with infinite values: {inf_columns}")

            # Проверка на отрицательные цены
            if "close" in features_data.columns:
                if (features_data["close"] <= 0).any():
                    errors.append("Close prices must be positive")

            # Проверка на отрицательные объемы
            if "volume" in features_data.columns:
                if (features_data["volume"] < 0).any():
                    errors.append("Volume must be non-negative")

            # Проверка возраста данных
            if "timestamp" in features_data.columns:
                latest_timestamp = features_data["timestamp"].max()
                if isinstance(latest_timestamp, pd.Timestamp):
                    age_hours = (
                        datetime.now() - latest_timestamp.to_pydatetime()
                    ).total_seconds() / 3600
                    if age_hours > self.config.max_age_hours:
                        warnings.append(
                            f"Data is {age_hours:.1f} hours old (max: {self.config.max_age_hours})"
                        )

            # Проверка на выбросы
            outlier_columns = self._detect_outliers(features_data)
            if outlier_columns:
                warnings.append(f"Potential outliers detected in: {outlier_columns}")

            # Определение статуса
            if errors:
                status = ValidationStatus.ERROR
            elif warnings:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID

            return ValidationResult(
                status=status,
                message=f"Features data validation: {status.value}",
                errors=errors,
                warnings=warnings,
                metadata={
                    "timeframe": timeframe,
                    "data_points": len(features_data),
                    "columns": list(features_data.columns),
                    "date_range": {
                        "start": (
                            features_data.index.min()
                            if hasattr(features_data.index, "min")
                            else None
                        ),
                        "end": (
                            features_data.index.max()
                            if hasattr(features_data.index, "max")
                            else None
                        ),
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error validating features data: {e}")
            return ValidationResult(
                status=ValidationStatus.ERROR,
                message=f"Features data validation error: {e!s}",
                errors=[str(e)],
                warnings=[],
                metadata={"timeframe": timeframe},
            )

    def validate_context_data(self, context_data: ContextData) -> ValidationResult:
        """Валидация данных контекста"""
        errors = []
        warnings = []

        try:
            # Валидация символа
            if not context_data.symbol or not isinstance(context_data.symbol, str):
                errors.append("Symbol must be a non-empty string")

            # Валидация таймфрейма
            if not context_data.timeframe or not isinstance(
                context_data.timeframe, str
            ):
                errors.append("Timeframe must be a non-empty string")

            # Валидация score
            if not isinstance(context_data.score, int | float):
                errors.append("Score must be a number")
            elif not -1.0 <= context_data.score <= 1.0:
                errors.append(
                    f"Score must be between -1.0 and 1.0, got {context_data.score}"
                )

            # Валидация режима
            if not isinstance(context_data.regime, RegimeType):
                errors.append(f"Invalid regime type: {context_data.regime}")

            # Валидация валидности
            if not isinstance(context_data.valid, bool):
                errors.append("Valid must be a boolean")

            # Валидация кодов причин
            if not isinstance(context_data.reason_codes, list):
                errors.append("Reason codes must be a list")
            else:
                for code in context_data.reason_codes:
                    if not isinstance(code, ReasonCode):
                        errors.append(f"Invalid reason code: {code}")

            # Валидация временной метки
            if not isinstance(context_data.timestamp, datetime):
                errors.append("Timestamp must be a datetime object")

            # Проверка логической согласованности
            if context_data.valid and not context_data.reason_codes:
                warnings.append("Valid context has no reason codes")

            if not context_data.valid and context_data.reason_codes:
                warnings.append("Invalid context has reason codes")

            # Проверка соответствия score и режима
            if (
                context_data.score > 0.3
                and context_data.regime == RegimeType.TREND_DOWN
            ):
                warnings.append("Positive score with bearish regime")
            elif (
                context_data.score < -0.3 and context_data.regime == RegimeType.TREND_UP
            ):
                warnings.append("Negative score with bullish regime")

            # Определение статуса
            if errors:
                status = ValidationStatus.ERROR
            elif warnings:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID

            return ValidationResult(
                status=status,
                message=f"Context data validation: {status.value}",
                errors=errors,
                warnings=warnings,
                metadata={
                    "symbol": context_data.symbol,
                    "timeframe": context_data.timeframe,
                    "score": context_data.score,
                    "regime": context_data.regime.value,
                    "valid": context_data.valid,
                    "reason_codes_count": len(context_data.reason_codes),
                },
            )

        except Exception as e:
            logger.error(f"Error validating context data: {e}")
            return ValidationResult(
                status=ValidationStatus.ERROR,
                message=f"Context data validation error: {e!s}",
                errors=[str(e)],
                warnings=[],
                metadata={},
            )

    def validate_context_result(self, result: ContextResult) -> ValidationResult:
        """Валидация результата контекста"""
        errors = []
        warnings = []

        try:
            # Валидация символа
            if not result.symbol or not isinstance(result.symbol, str):
                errors.append("Symbol must be a non-empty string")

            # Валидация временной метки
            if not isinstance(result.timestamp, datetime):
                errors.append("Timestamp must be a datetime object")

            # Валидация контекстов
            if not isinstance(result.contexts, dict):
                errors.append("Contexts must be a dictionary")
            elif not result.contexts:
                errors.append("Contexts dictionary is empty")
            else:
                for timeframe, context_data in result.contexts.items():
                    if not isinstance(context_data, ContextData):
                        errors.append(f"Invalid context data for timeframe {timeframe}")
                    else:
                        # Валидация каждого контекста
                        context_validation = self.validate_context_data(context_data)
                        if context_validation.status == ValidationStatus.ERROR:
                            errors.extend(
                                [
                                    f"{timeframe}: {err}"
                                    for err in context_validation.errors
                                ]
                            )
                        elif context_validation.status == ValidationStatus.WARNING:
                            warnings.extend(
                                [
                                    f"{timeframe}: {warn}"
                                    for warn in context_validation.warnings
                                ]
                            )

            # Валидация общего score
            if not isinstance(result.overall_score, int | float):
                errors.append("Overall score must be a number")
            elif not -1.0 <= result.overall_score <= 1.0:
                errors.append(
                    f"Overall score must be between -1.0 and 1.0, got {result.overall_score}"
                )

            # Валидация доминирующего режима
            if not isinstance(result.dominant_regime, RegimeType):
                errors.append(f"Invalid dominant regime type: {result.dominant_regime}")

            # Валидация уверенности
            if not isinstance(result.confidence, int | float):
                errors.append("Confidence must be a number")
            elif not 0.0 <= result.confidence <= 1.0:
                errors.append(
                    f"Confidence must be between 0.0 and 1.0, got {result.confidence}"
                )

            # Валидация валидности
            if not isinstance(result.valid, bool):
                errors.append("Valid must be a boolean")

            # Проверка согласованности
            if result.valid and result.has_errors:
                warnings.append("Valid result has errors")

            if not result.valid and not result.has_errors:
                warnings.append("Invalid result has no errors")

            # Проверка соответствия общего score и доминирующего режима
            if (
                result.overall_score > 0.3
                and result.dominant_regime == RegimeType.TREND_DOWN
            ):
                warnings.append("Positive overall score with bearish dominant regime")
            elif (
                result.overall_score < -0.3
                and result.dominant_regime == RegimeType.TREND_UP
            ):
                warnings.append("Negative overall score with bullish dominant regime")

            # Проверка консистентности по таймфреймам
            if len(result.contexts) > 1:
                regimes = [ctx.regime for ctx in result.contexts.values()]
                if len(set(regimes)) == 1:
                    # Все режимы одинаковые
                    if regimes[0] != result.dominant_regime:
                        warnings.append(
                            "Dominant regime doesn't match individual contexts"
                        )
                else:
                    # Режимы разные - проверяем логику
                    bullish_count = sum(
                        1 for regime in regimes if regime == RegimeType.TREND_UP
                    )
                    bearish_count = sum(
                        1 for regime in regimes if regime == RegimeType.TREND_DOWN
                    )

                    if (
                        bullish_count > bearish_count
                        and result.dominant_regime == RegimeType.TREND_DOWN
                    ):
                        warnings.append(
                            "More bullish contexts but bearish dominant regime"
                        )
                    elif (
                        bearish_count > bullish_count
                        and result.dominant_regime == RegimeType.TREND_UP
                    ):
                        warnings.append(
                            "More bearish contexts but bullish dominant regime"
                        )

            # Определение статуса
            if errors:
                status = ValidationStatus.ERROR
            elif warnings:
                status = ValidationStatus.WARNING
            else:
                status = ValidationStatus.VALID

            return ValidationResult(
                status=status,
                message=f"Context result validation: {status.value}",
                errors=errors,
                warnings=warnings,
                metadata={
                    "symbol": result.symbol,
                    "timeframes_count": len(result.contexts),
                    "overall_score": result.overall_score,
                    "dominant_regime": result.dominant_regime.value,
                    "confidence": result.confidence,
                    "valid": result.valid,
                    "has_errors": result.has_errors,
                },
            )

        except Exception as e:
            logger.error(f"Error validating context result: {e}")
            return ValidationResult(
                status=ValidationStatus.ERROR,
                message=f"Context result validation error: {e!s}",
                errors=[str(e)],
                warnings=[],
                metadata={},
            )

    def _detect_outliers(self, data: pd.DataFrame, threshold: float = 3.0) -> list[str]:
        """Обнаружение выбросов в данных"""
        outlier_columns = []

        try:
            numeric_columns = data.select_dtypes(include=[np.number]).columns

            for col in numeric_columns:
                if col in ["close", "high", "low", "open", "volume"]:
                    # Используем IQR метод для финансовых данных
                    Q1 = data[col].quantile(0.25)
                    Q3 = data[col].quantile(0.75)
                    IQR = Q3 - Q1

                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR

                    outliers = data[
                        (data[col] < lower_bound) | (data[col] > upper_bound)
                    ]

                    if len(outliers) > 0:
                        outlier_ratio = len(outliers) / len(data)
                        if outlier_ratio > 0.05:  # Более 5% выбросов
                            outlier_columns.append(col)
                else:
                    # Для других колонок используем Z-score
                    z_scores = np.abs((data[col] - data[col].mean()) / data[col].std())
                    outliers = data[z_scores > threshold]

                    if len(outliers) > 0:
                        outlier_ratio = len(outliers) / len(data)
                        if outlier_ratio > 0.05:  # Более 5% выбросов
                            outlier_columns.append(col)

        except Exception as e:
            logger.warning(f"Error detecting outliers: {e}")

        return outlier_columns

    def validate_data_quality(self, features_data: pd.DataFrame) -> dict[str, Any]:
        """Оценка качества данных"""
        quality_metrics = {
            "completeness": 0.0,
            "consistency": 0.0,
            "accuracy": 0.0,
            "timeliness": 0.0,
            "overall_score": 0.0,
        }

        try:
            # Полнота данных
            total_cells = features_data.size
            missing_cells = features_data.isnull().sum().sum()
            quality_metrics["completeness"] = (
                1.0 - (missing_cells / total_cells) if total_cells > 0 else 0.0
            )

            # Консистентность данных
            consistency_score = 1.0
            if "close" in features_data.columns:
                # Проверка на отрицательные цены
                negative_prices = (features_data["close"] <= 0).sum()
                if negative_prices > 0:
                    consistency_score -= 0.3

                # Проверка на резкие скачки цен
                if len(features_data) > 1:
                    price_changes = features_data["close"].pct_change().abs()
                    extreme_changes = (price_changes > 0.5).sum()  # Более 50% изменения
                    if extreme_changes > 0:
                        consistency_score -= 0.2

            if "volume" in features_data.columns:
                # Проверка на отрицательные объемы
                negative_volumes = (features_data["volume"] < 0).sum()
                if negative_volumes > 0:
                    consistency_score -= 0.3

            quality_metrics["consistency"] = max(0.0, consistency_score)

            # Точность данных (проверка на выбросы)
            outlier_columns = self._detect_outliers(features_data)
            accuracy_score = 1.0 - (len(outlier_columns) * 0.1)
            quality_metrics["accuracy"] = max(0.0, accuracy_score)

            # Своевременность данных
            if "timestamp" in features_data.columns:
                latest_timestamp = features_data["timestamp"].max()
                if isinstance(latest_timestamp, pd.Timestamp):
                    age_hours = (
                        datetime.now() - latest_timestamp.to_pydatetime()
                    ).total_seconds() / 3600
                    timeliness_score = max(
                        0.0, 1.0 - (age_hours / (self.config.max_age_hours * 2))
                    )
                    quality_metrics["timeliness"] = timeliness_score
                else:
                    quality_metrics["timeliness"] = 0.5  # Неизвестно
            else:
                quality_metrics["timeliness"] = 0.5  # Нет временной информации

            # Общий score
            quality_metrics["overall_score"] = (
                quality_metrics["completeness"] * 0.3
                + quality_metrics["consistency"] * 0.3
                + quality_metrics["accuracy"] * 0.2
                + quality_metrics["timeliness"] * 0.2
            )

        except Exception as e:
            logger.error(f"Error calculating data quality: {e}")
            quality_metrics["overall_score"] = 0.0

        return quality_metrics
