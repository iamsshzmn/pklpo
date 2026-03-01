"""
Валидатор для Triggers модуля
"""

from datetime import datetime, timedelta

import pandas as pd

from ..logging_config import get_triggers_logger
from .config import TriggersConfig
from .models import (
    AccelerationType,
    TriggerData,
    TriggersRequest,
    TriggersResult,
    ValidationResult,
    ValidationStatus,
)

logger = get_triggers_logger()


class TriggersValidator:
    """Валидатор для данных триггеров"""

    def __init__(self, config: TriggersConfig):
        self.config = config

    def validate_features_data(
        self, symbol: str, timeframe: str, features_data: pd.DataFrame
    ) -> ValidationResult:
        """Валидация входных данных индикаторов"""
        errors = []
        warnings = []
        metadata = {}

        if features_data.empty:
            errors.append("Features data is empty.")
            logger.warning(f"[{symbol}-{timeframe}] Features data is empty.")
            return ValidationResult(
                ValidationStatus.INVALID,
                "Empty features data",
                errors,
                warnings,
                metadata,
            )

        # Проверка на минимальное количество точек данных
        if len(features_data) < self.config.min_data_points:
            errors.append(
                f"Insufficient data points: {len(features_data)} < {self.config.min_data_points}"
            )
            logger.warning(
                f"[{symbol}-{timeframe}] Insufficient data points: {len(features_data)} < {self.config.min_data_points}"
            )

        # Проверка на наличие необходимых колонок для триггеров
        required_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "rsi_14",
            "macd",
            "atr",
        ]
        missing_columns = [
            col for col in required_columns if col not in features_data.columns
        ]
        if missing_columns:
            warnings.append(
                f"Missing required feature columns: {', '.join(missing_columns)}"
            )
            logger.warning(
                f"[{symbol}-{timeframe}] Missing required feature columns: {', '.join(missing_columns)}"
            )

        # Проверка на свежесть данных
        if hasattr(features_data.index, "max"):
            latest_timestamp = features_data.index.max()
            if isinstance(latest_timestamp, pd.Timestamp):
                if datetime.now() - latest_timestamp.to_pydatetime() > timedelta(
                    hours=self.config.max_age_hours
                ):
                    warnings.append(
                        f"Stale data: latest timestamp {latest_timestamp} is older than {self.config.max_age_hours} hours."
                    )
                    logger.warning(
                        f"[{symbol}-{timeframe}] Stale data: latest timestamp {latest_timestamp} is older than {self.config.max_age_hours} hours."
                    )

        # Проверка на наличие NaN значений в критических колонках
        critical_columns = ["close", "volume"]
        for col in critical_columns:
            if col in features_data.columns and features_data[col].isna().any():
                warnings.append(f"NaN values found in critical column: {col}")
                logger.warning(
                    f"[{symbol}-{timeframe}] NaN values found in critical column: {col}"
                )

        if errors:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Features data validation failed",
                errors,
                warnings,
                metadata,
            )
        if warnings:
            return ValidationResult(
                ValidationStatus.WARNING,
                "Features data has warnings",
                errors,
                warnings,
                metadata,
            )
        return ValidationResult(
            ValidationStatus.VALID,
            "Features data is valid",
            errors,
            warnings,
            metadata,
        )

    def validate_trigger_data(self, trigger_data: TriggerData) -> ValidationResult:
        """Валидация сгенерированных данных триггера"""
        errors = []
        warnings = []
        metadata = {}

        # Проверка вероятностей
        if not 0.0 <= trigger_data.p_up <= 1.0:
            errors.append(f"p_up out of range: {trigger_data.p_up}")
            logger.error(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] p_up out of range: {trigger_data.p_up}"
            )

        if not 0.0 <= trigger_data.p_down <= 1.0:
            errors.append(f"p_down out of range: {trigger_data.p_down}")
            logger.error(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] p_down out of range: {trigger_data.p_down}"
            )

        # Проверка anti-noise score
        if not 0.0 <= trigger_data.anti_noise_score <= 1.0:
            errors.append(
                f"anti_noise_score out of range: {trigger_data.anti_noise_score}"
            )
            logger.error(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] anti_noise_score out of range: {trigger_data.anti_noise_score}"
            )

        # Проверка confidence
        if not 0.0 <= trigger_data.confidence <= 1.0:
            errors.append(f"Confidence out of range: {trigger_data.confidence}")
            logger.error(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] Confidence out of range: {trigger_data.confidence}"
            )

        # Проверка типа ускорения
        if not isinstance(trigger_data.accel, AccelerationType):
            errors.append(f"Invalid acceleration type: {trigger_data.accel}")
            logger.error(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] Invalid acceleration type: {trigger_data.accel}"
            )

        # Проверка логической консистентности
        if (
            trigger_data.p_up + trigger_data.p_down > 1.2
        ):  # Допускаем небольшое превышение
            warnings.append(
                f"Sum of probabilities is high: {trigger_data.p_up + trigger_data.p_down}"
            )
            logger.warning(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] Sum of probabilities is high: {trigger_data.p_up + trigger_data.p_down}"
            )

        # Проверка на противоречивые сигналы
        if trigger_data.p_up > 0.7 and trigger_data.p_down > 0.7:
            warnings.append(
                "High probabilities in both directions - conflicting signals"
            )
            logger.warning(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] High probabilities in both directions - conflicting signals"
            )

        # Проверка микро-фильтра
        if trigger_data.micro_ok and trigger_data.confidence < 0.3:
            warnings.append("Micro filter passed but low confidence")
            logger.warning(
                f"[{trigger_data.symbol}-{trigger_data.timeframe}] Micro filter passed but low confidence"
            )

        if errors:
            return ValidationResult(
                ValidationStatus.ERROR,
                "Trigger data validation failed",
                errors,
                warnings,
                metadata,
            )
        if warnings:
            return ValidationResult(
                ValidationStatus.WARNING,
                "Trigger data has warnings",
                errors,
                warnings,
                metadata,
            )
        return ValidationResult(
            ValidationStatus.VALID,
            "Trigger data is valid",
            errors,
            warnings,
            metadata,
        )

    def validate_triggers_result(
        self, triggers_result: TriggersResult
    ) -> ValidationResult:
        """Валидация итогового результата построения триггеров"""
        errors = []
        warnings = []
        metadata = {}

        if not triggers_result.triggers:
            errors.append("No triggers were generated for any timeframe.")
            logger.error(
                f"[{triggers_result.symbol}] No triggers were generated for any timeframe."
            )

        # Проверка общих вероятностей
        if not 0.0 <= triggers_result.overall_p_up <= 1.0:
            errors.append(f"Overall p_up out of range: {triggers_result.overall_p_up}")
            logger.error(
                f"[{triggers_result.symbol}] Overall p_up out of range: {triggers_result.overall_p_up}"
            )

        if not 0.0 <= triggers_result.overall_p_down <= 1.0:
            errors.append(
                f"Overall p_down out of range: {triggers_result.overall_p_down}"
            )
            logger.error(
                f"[{triggers_result.symbol}] Overall p_down out of range: {triggers_result.overall_p_down}"
            )

        # Проверка эффективности фильтра шума
        if not 0.0 <= triggers_result.noise_filter_effectiveness <= 1.0:
            errors.append(
                f"Noise filter effectiveness out of range: {triggers_result.noise_filter_effectiveness}"
            )
            logger.error(
                f"[{triggers_result.symbol}] Noise filter effectiveness out of range: {triggers_result.noise_filter_effectiveness}"
            )

        # Проверка типа доминирующего ускорения
        if not isinstance(triggers_result.dominant_acceleration, AccelerationType):
            errors.append(
                f"Invalid dominant acceleration type: {triggers_result.dominant_acceleration}"
            )
            logger.error(
                f"[{triggers_result.symbol}] Invalid dominant acceleration type: {triggers_result.dominant_acceleration}"
            )

        # Агрегация ошибок и предупреждений из отдельных TriggerData
        for timeframe, trigger_data in triggers_result.triggers.items():
            trigger_validation = self.validate_trigger_data(trigger_data)
            if trigger_validation.status == ValidationStatus.ERROR:
                errors.extend([f"[{timeframe}] {e}" for e in trigger_validation.errors])
            elif trigger_validation.status == ValidationStatus.WARNING:
                warnings.extend(
                    [f"[{timeframe}] {w}" for w in trigger_validation.warnings]
                )

        # Проверка консистентности между таймфреймами
        if len(triggers_result.triggers) > 1:
            self._check_timeframe_consistency(triggers_result, warnings)

        # Проверка качества триггеров
        self._check_trigger_quality(triggers_result, warnings)

        if errors:
            return ValidationResult(
                ValidationStatus.ERROR,
                "Triggers result validation failed",
                errors,
                warnings,
                metadata,
            )
        if warnings:
            return ValidationResult(
                ValidationStatus.WARNING,
                "Triggers result has warnings",
                errors,
                warnings,
                metadata,
            )
        return ValidationResult(
            ValidationStatus.VALID,
            "Triggers result is valid",
            errors,
            warnings,
            metadata,
        )

    def validate_request(self, request: TriggersRequest) -> ValidationResult:
        """Валидация входящего запроса на построение триггеров"""
        errors = []
        warnings = []
        metadata = {}

        if not request.symbol:
            errors.append("Symbol cannot be empty.")
        if not request.timeframes:
            errors.append("Timeframes list cannot be empty.")

        # Проверка, что все запрошенные таймфреймы поддерживаются
        supported_timeframes = list(self.config.timeframe_weights.keys())
        unsupported_timeframes = [
            tf for tf in request.timeframes if tf not in supported_timeframes
        ]
        if unsupported_timeframes:
            warnings.append(
                f"Unsupported timeframes requested: {', '.join(unsupported_timeframes)}. These will be ignored."
            )
            logger.warning(
                f"[{request.symbol}] Unsupported timeframes requested: {', '.join(unsupported_timeframes)}. These will be ignored."
            )

        # Проверка данных features
        if request.features_data:
            for timeframe, features_df in request.features_data.items():
                if timeframe in request.timeframes:
                    features_validation = self.validate_features_data(
                        request.symbol, timeframe, features_df
                    )
                    if features_validation.status == ValidationStatus.INVALID:
                        errors.extend(
                            [f"[{timeframe}] {e}" for e in features_validation.errors]
                        )
                    elif features_validation.status == ValidationStatus.WARNING:
                        warnings.extend(
                            [f"[{timeframe}] {w}" for w in features_validation.warnings]
                        )

        if errors:
            return ValidationResult(
                ValidationStatus.INVALID,
                "Triggers request validation failed",
                errors,
                warnings,
                metadata,
            )
        if warnings:
            return ValidationResult(
                ValidationStatus.WARNING,
                "Triggers request has warnings",
                errors,
                warnings,
                metadata,
            )
        return ValidationResult(
            ValidationStatus.VALID,
            "Triggers request is valid",
            errors,
            warnings,
            metadata,
        )

    def _check_timeframe_consistency(
        self, triggers_result: TriggersResult, warnings: list[str]
    ):
        """Проверка консистентности между таймфреймами"""
        try:
            timeframes = list(triggers_result.triggers.keys())
            if len(timeframes) < 2:
                return

            # Проверка направления триггеров
            directions = []
            for _timeframe, trigger_data in triggers_result.triggers.items():
                if trigger_data.p_up > trigger_data.p_down:
                    directions.append(1)  # Bullish
                elif trigger_data.p_down > trigger_data.p_up:
                    directions.append(-1)  # Bearish
                else:
                    directions.append(0)  # Neutral

            # Проверка на противоречия
            unique_directions = set(directions)
            if len(unique_directions) > 2:  # Более 2 разных направлений
                warnings.append("Conflicting trigger directions across timeframes")
                logger.warning(
                    f"[{triggers_result.symbol}] Conflicting trigger directions across timeframes"
                )

            # Проверка на доминирующее направление
            directions.count(1)
            directions.count(-1)
            neutral_count = directions.count(0)

            if neutral_count > len(directions) / 2:
                warnings.append("Most timeframes show neutral signals")
                logger.warning(
                    f"[{triggers_result.symbol}] Most timeframes show neutral signals"
                )

        except Exception as e:
            logger.warning(f"Error checking timeframe consistency: {e}")

    def _check_trigger_quality(
        self, triggers_result: TriggersResult, warnings: list[str]
    ):
        """Проверка качества триггеров"""
        try:
            # Проверка силы сигналов
            weak_signals = 0
            strong_signals = 0

            for _timeframe, trigger_data in triggers_result.triggers.items():
                max_prob = max(trigger_data.p_up, trigger_data.p_down)
                if max_prob < 0.4:
                    weak_signals += 1
                elif max_prob > 0.7:
                    strong_signals += 1

            if weak_signals > len(triggers_result.triggers) / 2:
                warnings.append("Most triggers show weak signals")
                logger.warning(
                    f"[{triggers_result.symbol}] Most triggers show weak signals"
                )

            if strong_signals == 0:
                warnings.append("No strong trigger signals detected")
                logger.warning(
                    f"[{triggers_result.symbol}] No strong trigger signals detected"
                )

            # Проверка микро-фильтра
            micro_filter_passed = sum(
                1 for t in triggers_result.triggers.values() if t.micro_ok
            )
            micro_filter_rate = (
                micro_filter_passed / len(triggers_result.triggers)
                if triggers_result.triggers
                else 0
            )

            if micro_filter_rate < 0.5:
                warnings.append("Low micro filter pass rate")
                logger.warning(
                    f"[{triggers_result.symbol}] Low micro filter pass rate: {micro_filter_rate:.2f}"
                )

            # Проверка эффективности anti-noise фильтра
            if triggers_result.noise_filter_effectiveness < 0.5:
                warnings.append("Low noise filter effectiveness")
                logger.warning(
                    f"[{triggers_result.symbol}] Low noise filter effectiveness: {triggers_result.noise_filter_effectiveness:.2f}"
                )

        except Exception as e:
            logger.warning(f"Error checking trigger quality: {e}")

    def validate_config(self, config: TriggersConfig) -> ValidationResult:
        """Валидация конфигурации"""
        errors = []
        warnings = []
        metadata = {}

        try:
            # Проверка порогов вероятности
            if config.min_probability_threshold >= config.max_probability_threshold:
                errors.append(
                    "min_probability_threshold must be less than max_probability_threshold"
                )

            # Проверка весов компонентов
            total_weight = (
                config.momentum_weight
                + config.volume_weight
                + config.volatility_weight
                + config.support_resistance_weight
                + config.pattern_weight
            )

            if abs(total_weight - 1.0) > 0.01:
                warnings.append(
                    f"Sum of component weights is {total_weight}, should be 1.0"
                )

            # Проверка настроек фильтров
            if (
                config.micro_filter_threshold < 0.1
                or config.micro_filter_threshold > 0.9
            ):
                warnings.append("micro_filter_threshold should be between 0.1 and 0.9")

            if (
                config.noise_filter_threshold < 0.1
                or config.noise_filter_threshold > 0.9
            ):
                warnings.append("noise_filter_threshold should be between 0.1 and 0.9")

            # Проверка весов таймфреймов
            for timeframe, weight in config.timeframe_weights.items():
                if weight < 0.0 or weight > 1.0:
                    errors.append(
                        f"Weight for timeframe {timeframe} must be between 0.0 and 1.0"
                    )

        except Exception as e:
            errors.append(f"Error validating config: {e}")
            logger.error(f"Error validating config: {e}")

        if errors:
            return ValidationResult(
                ValidationStatus.ERROR,
                "Config validation failed",
                errors,
                warnings,
                metadata,
            )
        if warnings:
            return ValidationResult(
                ValidationStatus.WARNING,
                "Config has warnings",
                errors,
                warnings,
                metadata,
            )
        return ValidationResult(
            ValidationStatus.VALID, "Config is valid", errors, warnings, metadata
        )
