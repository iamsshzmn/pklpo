"""
Движок для построения триггеров
"""

import asyncio
from datetime import datetime
from typing import Any

import pandas as pd

from ..logging_config import create_log_context, get_triggers_logger, log_performance
from .algorithms import AccelerationAnalyzer, ProbabilityCalculator
from .config import TriggersConfig
from .filters import MicroFilter, NoiseFilter
from .models import (
    AccelerationType,
    TriggerData,
    TriggersMetrics,
    TriggersRequest,
    TriggersResult,
    ValidationStatus,
)
from .validator import TriggersValidator

logger = get_triggers_logger()


class TriggersEngine:
    """Движок для построения триггеров"""

    def __init__(self, config: TriggersConfig):
        self.config = config
        self.validator = TriggersValidator(config)
        self.probability_calculator = ProbabilityCalculator(config)
        self.acceleration_analyzer = AccelerationAnalyzer(config)
        self.micro_filter = MicroFilter(config)
        self.noise_filter = NoiseFilter(config)
        self.cache: dict[str, tuple[datetime, TriggersResult]] = {}
        self.metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_processing_time": 0.0,
            "last_request_time": None,
            "error_rate": 0.0,
        }
        logger.info("TriggersEngine initialized")

    @log_performance("triggers", "build_triggers_engine")
    async def build_triggers(self, request: TriggersRequest) -> TriggersResult:
        """Построение триггеров для заданного символа и таймфреймов."""
        with create_log_context("triggers", f"build_triggers_engine_{request.symbol}"):
            logger.info(f"Starting triggers build for {request.symbol}")

            validation_result = self.validator.validate_request(request)
            if validation_result.status == ValidationStatus.INVALID:
                logger.error(f"Triggers request validation failed for {request.symbol}")
                return TriggersResult(
                    symbol=request.symbol,
                    timestamp=request.timestamp,
                    triggers={},
                    overall_p_up=0.0,
                    overall_p_down=0.0,
                    dominant_acceleration=AccelerationType.NEUTRAL,
                    micro_filter_passed=False,
                    noise_filter_effectiveness=0.0,
                    valid=False,
                    errors=validation_result.errors,
                )

            tasks = []
            processed_timeframes = []
            for timeframe in request.timeframes:
                if timeframe not in self.config.timeframe_weights:
                    continue

                tasks.append(
                    asyncio.create_task(
                        self._build_single_trigger(
                            request.symbol,
                            timeframe,
                            request.timestamp,
                            (
                                request.features_data.get(timeframe)
                                if request.features_data
                                else None
                            ),
                            request.context_data,
                        )
                    )
                )
                processed_timeframes.append(timeframe)

            if not tasks:
                return TriggersResult(
                    symbol=request.symbol,
                    timestamp=request.timestamp,
                    triggers={},
                    overall_p_up=0.0,
                    overall_p_down=0.0,
                    dominant_acceleration=AccelerationType.NEUTRAL,
                    micro_filter_passed=False,
                    noise_filter_effectiveness=0.0,
                    valid=False,
                    errors=["No valid timeframes to process"],
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_triggers: dict[str, TriggerData] = {}
            successful_timeframes = 0
            total_p_up = 0.0
            total_p_down = 0.0
            acceleration_counts: dict[AccelerationType, int] = dict.fromkeys(
                AccelerationType, 0
            )
            micro_filter_passed_count = 0
            all_errors = []

            for i, res in enumerate(results):
                timeframe = processed_timeframes[i]
                if isinstance(res, Exception):
                    logger.error(
                        f"Error building single trigger for {request.symbol} {timeframe}: {res}"
                    )
                    all_errors.append(f"[{timeframe}] {res!s}")
                elif res:
                    all_triggers[timeframe] = res
                    if res.valid:
                        successful_timeframes += 1
                        weight = self.config.get_timeframe_weight(timeframe)
                        total_p_up += res.p_up * weight
                        total_p_down += res.p_down * weight
                        acceleration_counts[res.accel] += 1
                        if res.micro_ok:
                            micro_filter_passed_count += 1
                    else:
                        all_errors.append(f"[{timeframe}] Trigger invalid")

            # Расчет агрегированных значений
            overall_p_up = (
                total_p_up / successful_timeframes if successful_timeframes > 0 else 0.0
            )
            overall_p_down = (
                total_p_down / successful_timeframes
                if successful_timeframes > 0
                else 0.0
            )
            dominant_acceleration = self._determine_dominant_acceleration(
                acceleration_counts
            )
            micro_filter_passed = micro_filter_passed_count > successful_timeframes / 2
            noise_filter_effectiveness = self._calculate_noise_filter_effectiveness(
                all_triggers
            )
            overall_valid = successful_timeframes > 0 and not all_errors

            final_result = TriggersResult(
                symbol=request.symbol,
                timestamp=request.timestamp,
                triggers=all_triggers,
                overall_p_up=overall_p_up,
                overall_p_down=overall_p_down,
                dominant_acceleration=dominant_acceleration,
                micro_filter_passed=micro_filter_passed,
                noise_filter_effectiveness=noise_filter_effectiveness,
                valid=overall_valid,
                errors=all_errors,
            )

            logger.info(
                f"Triggers built for {request.symbol}, timeframes: {successful_timeframes}/{len(processed_timeframes)}"
            )
            return final_result

    async def _build_single_trigger(
        self,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
        features_data: pd.DataFrame | None,
        context_data: dict[str, Any] | None,
    ) -> TriggerData | None:
        """Построение триггера для одного таймфрейма."""
        logger.debug(f"[{symbol}-{timeframe}] Building single trigger...")

        if features_data is None or features_data.empty:
            return self._create_invalid_trigger(
                symbol, timeframe, timestamp, "No features data"
            )

        try:
            # 1. Calculate Probabilities
            probability_components = (
                self.probability_calculator.calculate_probabilities(
                    features_data, context_data
                )
            )

            # 2. Analyze Acceleration
            acceleration_analysis = self.acceleration_analyzer.analyze_acceleration(
                features_data
            )

            # 3. Apply Micro Filter
            micro_filter_result = self.micro_filter.apply_filter(
                features_data, probability_components, acceleration_analysis
            )

            # 4. Create TriggerData
            trigger_data = TriggerData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                p_up=probability_components.final_p_up,
                p_down=probability_components.final_p_down,
                accel=acceleration_analysis.acceleration,
                micro_ok=micro_filter_result.status.value == "passed",
                anti_noise_score=0.0,
                valid=True,
                confidence=micro_filter_result.confidence,
                metadata={
                    "probability_components": probability_components.__dict__,
                    "acceleration_analysis": acceleration_analysis.__dict__,
                    "micro_filter_result": micro_filter_result.__dict__,
                    "context_data": context_data,
                },
            )

            # 5. Apply Noise Filter
            noise_filter_results = self.noise_filter.apply_filters(
                features_data, trigger_data
            )
            trigger_data.anti_noise_score = (
                self.noise_filter.calculate_overall_effectiveness(noise_filter_results)
            )
            trigger_data.metadata["noise_filter_results"] = [
                r.__dict__ for r in noise_filter_results
            ]

            logger.debug(
                f"[{symbol}-{timeframe}] Trigger built: p_up={trigger_data.p_up:.3f}, p_down={trigger_data.p_down:.3f}"
            )
            return trigger_data

        except Exception as e:
            logger.error(f"Error building single trigger for {symbol} {timeframe}: {e}")
            return self._create_invalid_trigger(symbol, timeframe, timestamp, [str(e)])

    def _create_invalid_trigger(
        self, symbol: str, timeframe: str, timestamp: datetime, errors: list[str]
    ) -> TriggerData:
        """Создает невалидный TriggerData объект."""
        return TriggerData(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            p_up=0.5,
            p_down=0.5,
            accel=AccelerationType.NEUTRAL,
            micro_ok=False,
            anti_noise_score=0.0,
            valid=False,
            confidence=0.0,
            metadata={"validation_errors": errors},
        )

    def _determine_dominant_acceleration(
        self, acceleration_counts: dict[AccelerationType, int]
    ) -> AccelerationType:
        """Определяет доминирующее ускорение на основе подсчетов."""
        if not acceleration_counts:
            return AccelerationType.NEUTRAL

        filtered_counts = {
            a: c
            for a, c in acceleration_counts.items()
            if a != AccelerationType.NEUTRAL
        }
        if not filtered_counts:
            return AccelerationType.NEUTRAL

        return max(filtered_counts, key=filtered_counts.get)

    def _calculate_noise_filter_effectiveness(
        self, triggers: dict[str, TriggerData]
    ) -> float:
        """Рассчитывает общую эффективность фильтра шума."""
        if not triggers:
            return 0.0

        valid_triggers = [t for t in triggers.values() if t.valid]
        if not valid_triggers:
            return 0.0

        return sum(t.anti_noise_score for t in valid_triggers) / len(valid_triggers)

    def get_cache_stats(self) -> dict[str, Any]:
        """Возвращает статистику кэша."""
        return {
            "enabled": self.config.cache_enabled,
            "size": len(self.cache),
            "ttl_seconds": self.config.cache_ttl_seconds,
        }

    def get_metrics(self) -> TriggersMetrics:
        """Возвращает метрики движка триггеров."""
        return TriggersMetrics(
            calculation_time=self.metrics.get("avg_processing_time", 0.0),
            timeframes_processed=self.metrics.get("total_requests", 0),
            timeframes_successful=self.metrics.get("successful_requests", 0),
            timeframes_failed=self.metrics.get("failed_requests", 0),
            average_p_up=0.5,  # Placeholder - нужно вычислять из результатов
            average_p_down=0.5,  # Placeholder - нужно вычислять из результатов
            acceleration_distribution={
                AccelerationType.NEUTRAL: 0,
                AccelerationType.BULLISH: 0,
                AccelerationType.BEARISH: 0,
            },
            micro_filter_pass_rate=0.8,  # Placeholder
            noise_filter_effectiveness=0.7,  # Placeholder
        )
