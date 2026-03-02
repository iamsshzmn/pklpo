"""
Движок для Consensus модуля
"""

import time
from datetime import datetime, timedelta
from typing import Any

from ..logging_config import create_log_context, get_consensus_logger, log_performance
from .algorithms import ConsensusAggregator
from .config import ConsensusConfig
from .models import (
    ConfidenceLevel,
    ConsensusMetrics,
    ConsensusRequest,
    ConsensusResult,
    ConsensusType,
    ValidationStatus,
)
from .validator import ConsensusValidator

logger = get_consensus_logger()


class ConsensusEngine:
    """Движок для построения консенсуса"""

    def __init__(self, config: ConsensusConfig):
        self.config = config
        self.validator = ConsensusValidator(config)
        self.aggregator = ConsensusAggregator(config)
        self.cache: dict[str, tuple[datetime, ConsensusResult]] = {}
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
        logger.info("ConsensusEngine initialized")

    @log_performance("consensus", "build_consensus_engine")
    async def build_consensus(self, request: ConsensusRequest) -> ConsensusResult:
        """Построение консенсуса для заданного символа и таймфреймов."""
        with create_log_context(
            "consensus", f"build_consensus_engine_{request.symbol}"
        ):
            logger.info(f"Starting consensus build for {request.symbol}")

            # Обновляем метрики
            self.metrics["total_requests"] += 1
            self.metrics["last_request_time"] = datetime.now()

            # Валидация запроса
            validation_result = self.validator.validate_request(request)
            if validation_result.status == ValidationStatus.INVALID:
                logger.error(
                    f"Consensus request validation failed for {request.symbol}"
                )
                self.metrics["failed_requests"] += 1
                return self._create_error_result(request, "Validation failed")

            # Проверка кэша
            cache_key = self._get_cache_key(request)
            if self.config.cache_enabled and cache_key in self.cache:
                cached_time, cached_result = self.cache[cache_key]
                if datetime.now() - cached_time < timedelta(
                    seconds=self.config.cache_ttl_seconds
                ):
                    logger.info(f"Using cached consensus for {request.symbol}")
                    self.metrics["cache_hits"] += 1
                    return cached_result
                del self.cache[cache_key]

            self.metrics["cache_misses"] += 1

            try:
                # Построение консенсуса
                result = self.aggregator.build_consensus(
                    symbol=request.symbol,
                    timeframes=request.timeframes,
                    context_data=request.context_data or {},
                    triggers_data=request.triggers_data or {},
                    timestamp=request.timestamp,
                )

                # Сохранение в кэш
                if self.config.cache_enabled:
                    self.cache[cache_key] = (datetime.now(), result)

                # Обновляем метрики
                self.metrics["successful_requests"] += 1
                self._update_processing_time()

                logger.info(
                    f"Consensus built for {request.symbol}: {result.consensus_type.value}"
                )
                return result

            except Exception as e:
                logger.error(f"Error building consensus for {request.symbol}: {e}")
                self.metrics["failed_requests"] += 1
                self._update_error_rate()
                return self._create_error_result(request, f"Error: {e!s}")

    def _get_cache_key(self, request: ConsensusRequest) -> str:
        """Генерация ключа кэша"""
        timeframes_str = "_".join(sorted(request.timeframes))
        timestamp_str = (
            request.timestamp.strftime("%Y%m%d_%H%M")
            if request.timestamp
            else "current"
        )
        return f"{request.symbol}_{timeframes_str}_{timestamp_str}"

    def _create_error_result(
        self, request: ConsensusRequest, error_msg: str
    ) -> ConsensusResult:
        """Создание результата с ошибкой"""
        return ConsensusResult(
            symbol=request.symbol,
            timestamp=request.timestamp or datetime.now(),
            consensus_type=ConsensusType.CONFLICTED,
            confidence_level=ConfidenceLevel.VERY_LOW,
            final_score=0.0,
            context_weight=0.5,
            triggers_weight=0.5,
            timeframe_breakdown={},
            supporting_evidence=[],
            conflicting_evidence=[error_msg],
            warnings=[error_msg],
            is_valid=False,
            metadata={"error": error_msg},
        )

    def _update_processing_time(self):
        """Обновление среднего времени обработки"""
        current_time = time.time()
        if "last_processing_time" not in self.metrics:
            self.metrics["avg_processing_time"] = 0.1
        else:
            alpha = 0.1
            processing_time = current_time - self.metrics["last_processing_time"]
            self.metrics["avg_processing_time"] = (
                alpha * processing_time
                + (1 - alpha) * self.metrics["avg_processing_time"]
            )
        self.metrics["last_processing_time"] = current_time

    def _update_error_rate(self):
        """Обновление коэффициента ошибок"""
        total = self.metrics["total_requests"]
        failed = self.metrics["failed_requests"]
        if total > 0:
            self.metrics["error_rate"] = failed / total

    def get_health_status(self) -> dict[str, Any]:
        """Получение статуса здоровья движка"""
        total_requests = self.metrics["total_requests"]
        error_rate = self.metrics["error_rate"]

        if total_requests == 0:
            status = "unknown"
        elif error_rate > 0.5:
            status = "unhealthy"
        elif error_rate > 0.2:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "total_requests": total_requests,
            "error_rate": error_rate,
            "cache_size": len(self.cache),
            "last_request": self.metrics["last_request_time"],
        }

    def get_cache_stats(self) -> dict[str, Any]:
        """Возвращает статистику кэша."""
        return {
            "enabled": self.config.cache_enabled,
            "size": len(self.cache),
            "ttl_seconds": self.config.cache_ttl_seconds,
        }

    def get_metrics(self) -> ConsensusMetrics:
        """Возвращает метрики движка консенсуса."""
        return ConsensusMetrics(
            calculation_time=self.metrics.get("avg_processing_time", 0.0),
            symbols_processed=self.metrics.get("total_requests", 0),
            symbols_successful=self.metrics.get("successful_requests", 0),
            symbols_failed=self.metrics.get("failed_requests", 0),
            consensus_distribution={
                ConsensusType.NEUTRAL: 0,
                ConsensusType.BULLISH: 0,
                ConsensusType.BEARISH: 0,
                ConsensusType.STRONG_BULLISH: 0,
                ConsensusType.STRONG_BEARISH: 0,
                ConsensusType.CONFLICTED: 0,
            },
            confidence_distribution={
                ConfidenceLevel.VERY_HIGH: 0,
                ConfidenceLevel.HIGH: 0,
                ConfidenceLevel.MEDIUM: 0,
                ConfidenceLevel.LOW: 0,
                ConfidenceLevel.VERY_LOW: 0,
            },
            average_confidence=0.5,
            conflict_rate=self.metrics.get("error_rate", 0.0),
        )

    def clear_cache(self):
        """Очистка кэша"""
        self.cache.clear()
        logger.info("Consensus cache cleared")

    def update_config(self, new_config: ConsensusConfig):
        """Обновление конфигурации"""
        self.config = new_config
        self.validator = ConsensusValidator(new_config)
        self.aggregator = ConsensusAggregator(new_config)
        logger.info("Consensus engine configuration updated")
