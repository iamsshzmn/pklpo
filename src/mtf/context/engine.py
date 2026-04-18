"""
Engine for Context Builder
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .algorithms import (
    EnhancedTrendScoreCalculator,
    ReasonCodeGenerator,
    RegimeDetector,
)
from .config import ContextConfig
from .models import (
    ContextData,
    ContextMetrics,
    ContextRequest,
    ContextResult,
    ReasonCode,
    RegimeAnalysis,
    RegimeType,
    TrendScoreComponents,
)
from .validator import ContextValidator

logger = logging.getLogger(__name__)


class ContextEngine:
    """Context building engine"""

    def __init__(self, config: ContextConfig):
        self.config = config
        self.validator = ContextValidator(config)
        self.trend_calculator = EnhancedTrendScoreCalculator(config)
        self.reason_generator = ReasonCodeGenerator(config)
        self.regime_detector = RegimeDetector(config.to_dict())

        # Result cache
        self._cache = {} if config.cache_enabled else None
        self._cache_ttl = config.cache_ttl_seconds

    async def build_context(self, request: ContextRequest) -> ContextResult:
        """Build context for request"""
        start_time = datetime.now()

        try:
            # Validate request
            request_validation = self.validator.validate_request(request)
            if request_validation.status.value == "error":
                return ContextResult(
                    symbol=request.symbol,
                    timestamp=request.timestamp or datetime.now(),
                    contexts={},
                    overall_score=0.0,
                    dominant_regime=RegimeType.UNKNOWN,
                    confidence=0.0,
                    valid=False,
                    errors=request_validation.errors,
                )

            # Check cache
            cache_key = self._get_cache_key(request)
            if self._cache and cache_key in self._cache:
                cached_result, cached_time = self._cache[cache_key]
                if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                    logger.debug(f"Using cached context for {request.symbol}")
                    return cached_result

            # Build contexts for each timeframe
            contexts = {}
            errors = []

            if self.config.max_workers > 1:
                # Parallel execution
                contexts, errors = await self._build_contexts_parallel(request)
            else:
                # Sequential execution
                contexts, errors = await self._build_contexts_sequential(request)

            # Aggregate results
            overall_score, dominant_regime, confidence = self._aggregate_contexts(
                contexts
            )

            # Build result
            result = ContextResult(
                symbol=request.symbol,
                timestamp=request.timestamp or datetime.now(),
                contexts=contexts,
                overall_score=overall_score,
                dominant_regime=dominant_regime,
                confidence=confidence,
                valid=len(contexts) > 0 and len(errors) == 0,
                errors=errors,
            )

            # Validate result
            result_validation = self.validator.validate_context_result(result)
            if result_validation.status.value == "error":
                result.errors.extend(result_validation.errors)
                result.valid = False

            # Save to cache
            if self._cache:
                self._cache[cache_key] = (result, datetime.now())

            # Log metrics
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Context built for {request.symbol} in {duration:.2f}s, "
                f"timeframes: {len(contexts)}, valid: {result.valid}"
            )

            return result

        except Exception as e:
            logger.error(f"Error building context for {request.symbol}: {e}")
            return ContextResult(
                symbol=request.symbol,
                timestamp=request.timestamp or datetime.now(),
                contexts={},
                overall_score=0.0,
                dominant_regime=RegimeType.UNKNOWN,
                confidence=0.0,
                valid=False,
                errors=[str(e)],
            )

    async def _build_contexts_parallel(
        self, request: ContextRequest
    ) -> tuple[dict[str, ContextData], list[str]]:
        """Build contexts in parallel"""
        contexts = {}
        errors = []

        # Create tasks for each timeframe
        tasks = []
        for timeframe in request.timeframes:
            task = asyncio.create_task(
                self._build_single_context(
                    request.symbol, timeframe, request.features_data
                )
            )
            tasks.append((timeframe, task))

        # Wait for all tasks
        for timeframe, task in tasks:
            try:
                context_data = await asyncio.wait_for(
                    task, timeout=self.config.timeout_seconds
                )
                if context_data:
                    contexts[timeframe] = context_data
                else:
                    errors.append(f"Failed to build context for {timeframe}")
            except TimeoutError:
                errors.append(f"Timeout building context for {timeframe}")
            except Exception as e:
                errors.append(f"Error building context for {timeframe}: {e!s}")

        return contexts, errors

    async def _build_contexts_sequential(
        self, request: ContextRequest
    ) -> tuple[dict[str, ContextData], list[str]]:
        """Build contexts sequentially"""
        contexts = {}
        errors = []

        for timeframe in request.timeframes:
            try:
                context_data = await self._build_single_context(
                    request.symbol, timeframe, request.features_data
                )
                if context_data:
                    contexts[timeframe] = context_data
                else:
                    errors.append(f"Failed to build context for {timeframe}")
            except Exception as e:
                errors.append(f"Error building context for {timeframe}: {e!s}")

        return contexts, errors

    async def _build_single_context(
        self,
        symbol: str,
        timeframe: str,
        features_data: dict[str, pd.DataFrame] | None,
    ) -> ContextData | None:
        """Build context for one timeframe"""
        try:
            # Fetch timeframe data
            if not features_data or timeframe not in features_data:
                logger.warning(f"No features data for {symbol} {timeframe}")
                return None

            tf_data = features_data[timeframe]

            # Validate data
            data_validation = self.validator.validate_features_data(tf_data, timeframe)
            if data_validation.status.value == "error":
                logger.error(
                    f"Invalid features data for {symbol} {timeframe}: {data_validation.errors}"
                )
                return None

            # Calculate trend score
            trend_components = self.trend_calculator.calculate_trend_score(tf_data)

            # Analyze regime
            regime_analysis = self.regime_detector.detect_regime(
                tf_data.iloc[-1].to_dict(), trend_components.final_score
            )

            # Generate reason codes
            reason_codes = self.reason_generator.generate_reason_codes(
                trend_components, tf_data
            )

            # Determine validity
            is_valid = self._determine_validity(
                trend_components, regime_analysis, reason_codes
            )

            # Build context
            return ContextData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(),
                score=trend_components.final_score,
                regime=regime_analysis.regime,
                valid=is_valid,
                reason_codes=reason_codes,
                meta={
                    "trend_components": {
                        "ema_trend": trend_components.ema_trend,
                        "adx_strength": trend_components.adx_strength,
                        "rsi_momentum": trend_components.rsi_momentum,
                        "macd_signal": trend_components.macd_signal,
                        "volume_confirmation": trend_components.volume_confirmation,
                        "volatility_factor": trend_components.volatility_factor,
                    },
                    "regime_analysis": {
                        "confidence": regime_analysis.confidence,
                        "trend_strength": regime_analysis.trend_strength,
                        "volatility_level": regime_analysis.volatility_level,
                        "volume_profile": regime_analysis.volume_profile,
                        "reasoning": regime_analysis.reasoning,
                    },
                    "data_quality": self.validator.validate_data_quality(tf_data),
                },
            )

        except Exception as e:
            logger.error(f"Error building single context for {symbol} {timeframe}: {e}")
            return None

    def _determine_validity(
        self,
        trend_components: TrendScoreComponents,
        regime_analysis: RegimeAnalysis,
        reason_codes: list[ReasonCode],
    ) -> bool:
        """Determine context validity"""
        # Basic validity conditions
        if not reason_codes:
            return False

        if ReasonCode.INSUFFICIENT_DATA in reason_codes:
            return False

        # Check for conflicting signals
        if ReasonCode.CONFLICTING_SIGNALS in reason_codes:
            return False

        # Check minimum confidence
        if regime_analysis.confidence < 0.3:
            return False

        # Check minimum score
        if abs(trend_components.final_score) < 0.1:
            return False

        # Check volatility
        return not trend_components.volatility_factor < 0.5

    def _aggregate_contexts(
        self, contexts: dict[str, ContextData]
    ) -> tuple[float, RegimeType, float]:
        """Aggregate contexts into final result"""
        if not contexts:
            return 0.0, RegimeType.UNKNOWN, 0.0

        # Weighted score aggregation
        total_weight = 0.0
        weighted_score = 0.0

        for timeframe, context in contexts.items():
            weight = self.config.get_timeframe_weight(timeframe)
            weighted_score += context.score * weight
            total_weight += weight

        overall_score = weighted_score / total_weight if total_weight > 0 else 0.0

        # Determine dominant regime
        regime_counts = {}
        regime_weights = {}

        for timeframe, context in contexts.items():
            regime = context.regime
            weight = self.config.get_timeframe_weight(timeframe)

            if regime not in regime_counts:
                regime_counts[regime] = 0
                regime_weights[regime] = 0.0

            regime_counts[regime] += 1
            regime_weights[regime] += weight

        # Select regime with highest weight
        dominant_regime = max(regime_weights.items(), key=lambda x: x[1])[0]

        # Calculate overall confidence
        confidence_scores = []
        for context in contexts.values():
            if "regime_analysis" in context.meta:
                confidence_scores.append(context.meta["regime_analysis"]["confidence"])

        overall_confidence = np.mean(confidence_scores) if confidence_scores else 0.0

        return overall_score, dominant_regime, overall_confidence

    def _get_cache_key(self, request: ContextRequest) -> str:
        """Generate cache key"""
        key_parts = [
            request.symbol,
            ",".join(sorted(request.timeframes)),
            str(request.timestamp.date()) if request.timestamp else "today",
        ]
        return "|".join(key_parts)

    def clear_cache(self) -> None:
        """Clear cache"""
        if self._cache:
            self._cache.clear()
            logger.info("Context cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        if not self._cache:
            return {"enabled": False}

        now = datetime.now()
        valid_entries = 0
        expired_entries = 0

        for _key, (_result, cached_time) in self._cache.items():
            if (now - cached_time).total_seconds() < self._cache_ttl:
                valid_entries += 1
            else:
                expired_entries += 1

        return {
            "enabled": True,
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_ttl_seconds": self._cache_ttl,
        }

    async def get_context_metrics(
        self, symbol: str, timeframes: list[str]
    ) -> ContextMetrics:
        """Get context metrics"""
        start_time = datetime.now()

        try:
            # Build request for metrics
            request = ContextRequest(
                symbol=symbol, timeframes=timeframes, timestamp=datetime.now()
            )

            # Build context
            result = await self.build_context(request)

            # Calculate metrics
            calculation_time = (datetime.now() - start_time).total_seconds()

            timeframes_processed = len(timeframes)
            timeframes_successful = len(result.contexts)
            timeframes_failed = timeframes_processed - timeframes_successful

            # Regime distribution
            regime_distribution = {}
            for context in result.contexts.values():
                regime = context.regime
                regime_distribution[regime] = regime_distribution.get(regime, 0) + 1

            # Reason code distribution
            reason_code_distribution = {}
            for context in result.contexts.values():
                for code in context.reason_codes:
                    reason_code_distribution[code] = (
                        reason_code_distribution.get(code, 0) + 1
                    )

            # Average score
            if result.contexts:
                average_score = np.mean([ctx.score for ctx in result.contexts.values()])
            else:
                average_score = 0.0

            return ContextMetrics(
                calculation_time=calculation_time,
                timeframes_processed=timeframes_processed,
                timeframes_successful=timeframes_successful,
                timeframes_failed=timeframes_failed,
                average_score=average_score,
                regime_distribution=regime_distribution,
                reason_code_distribution=reason_code_distribution,
            )

        except Exception as e:
            logger.error(f"Error getting context metrics for {symbol}: {e}")
            return ContextMetrics(
                calculation_time=0.0,
                timeframes_processed=0,
                timeframes_successful=0,
                timeframes_failed=0,
                average_score=0.0,
                regime_distribution={},
                reason_code_distribution={},
            )

    def update_config(self, new_config: ContextConfig) -> None:
        """Update configuration"""
        self.config = new_config
        self.validator = ContextValidator(new_config)
        self.trend_calculator = EnhancedTrendScoreCalculator(new_config)
        self.reason_generator = ReasonCodeGenerator(new_config)
        self.regime_detector = RegimeDetector(new_config.to_dict())

        # Update cache settings
        if not new_config.cache_enabled and self._cache:
            self._cache = None
        elif new_config.cache_enabled and not self._cache:
            self._cache = {}

        self._cache_ttl = new_config.cache_ttl_seconds

        logger.info("Context engine configuration updated")
