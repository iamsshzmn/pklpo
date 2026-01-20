"""
Core processing engine for MTF Pipeline module
"""

import uuid
from datetime import datetime
from typing import Any

from ..consensus.builder import ConsensusBuilder
from ..context.builder import ContextBuilder
from ..logging_config import create_log_context, get_pipeline_logger
from ..triggers.builder import TriggersBuilder
from .models import (
    PipelineConfig,
    PipelineMetrics,
    PipelineRequest,
    PipelineResult,
    PipelineStatus,
    ProcessingStage,
)


class PipelineEngine:
    """Движок обработки pipeline"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = get_pipeline_logger()

        # Инициализация компонентов
        self.context_builder = None
        self.triggers_builder = None
        self.consensus_builder = None

        # Метрики
        self.metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cancelled_requests": 0,
            "processing_times": [],
            "context_times": [],
            "triggers_times": [],
            "consensus_times": [],
            "context_successes": 0,
            "triggers_successes": 0,
            "consensus_successes": 0,
            "context_errors": 0,
            "triggers_errors": 0,
            "consensus_errors": 0,
            "symbols_processed": set(),
            "timeframes_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Кэш результатов
        self.cache: dict[str, PipelineResult] = {}

        self.logger.info("PipelineEngine initialized")

    async def initialize_components(self) -> None:
        """Инициализация компонентов"""
        try:
            if self.config.context_enabled:
                from ..context.config import ContextConfig

                context_config = ContextConfig.default()
                self.context_builder = ContextBuilder(context_config)
                self.logger.info("Context builder initialized")

            if self.config.triggers_enabled:
                from ..triggers.config import TriggersConfig

                triggers_config = TriggersConfig.default()
                self.triggers_builder = TriggersBuilder(triggers_config)
                self.logger.info("Triggers builder initialized")

            if self.config.consensus_enabled:
                from ..consensus.config import ConsensusConfig

                consensus_config = ConsensusConfig.default()
                self.consensus_builder = ConsensusBuilder(consensus_config)
                self.logger.info("Consensus builder initialized")

            self.logger.info("All components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise

    async def process_request(self, request: PipelineRequest) -> PipelineResult:
        """Обработка запроса pipeline"""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = datetime.now()

        result = PipelineResult(
            request_id=request_id,
            symbol=request.symbol,
            timeframes=request.timeframes,
            status=PipelineStatus.PENDING,
            processing_stage=ProcessingStage.INITIALIZED,
            start_time=start_time,
        )

        try:
            # Обновление метрик
            self.metrics["total_requests"] += 1
            self.metrics["symbols_processed"].add(request.symbol)
            self.metrics["timeframes_processed"] += len(request.timeframes)

            # Проверка кэша
            cache_key = self._generate_cache_key(request)
            if self.config.cache_enabled and cache_key in self.cache:
                self.metrics["cache_hits"] += 1
                cached_result = self.cache[cache_key]
                cached_result.request_id = request_id
                cached_result.start_time = start_time
                cached_result.end_time = datetime.now()
                return cached_result
            self.metrics["cache_misses"] += 1

            # Инициализация компонентов если нужно
            if not self._are_components_initialized():
                await self.initialize_components()

            # Обработка по стадиям
            result.status = PipelineStatus.RUNNING

            # Стадия 1: Context
            if self.config.context_enabled and self.context_builder:
                result.processing_stage = ProcessingStage.CONTEXT_BUILDING
                context_result = await self._build_context(request)
                result.context_result = context_result

                if context_result and context_result.is_valid:
                    self.metrics["context_successes"] += 1
                else:
                    self.metrics["context_errors"] += 1
                    result.warnings.append(
                        "Context building failed or returned invalid result"
                    )

            # Стадия 2: Triggers
            if self.config.triggers_enabled and self.triggers_builder:
                result.processing_stage = ProcessingStage.TRIGGERS_BUILDING
                triggers_result = await self._build_triggers(request)
                result.triggers_result = triggers_result

                if triggers_result and triggers_result.is_valid:
                    self.metrics["triggers_successes"] += 1
                else:
                    self.metrics["triggers_errors"] += 1
                    result.warnings.append(
                        "Triggers building failed or returned invalid result"
                    )

            # Стадия 3: Consensus
            if self.config.consensus_enabled and self.consensus_builder:
                result.processing_stage = ProcessingStage.CONSENSUS_BUILDING
                consensus_result = await self._build_consensus(request, result)
                result.consensus_result = consensus_result

                if consensus_result and consensus_result.is_valid:
                    self.metrics["consensus_successes"] += 1
                else:
                    self.metrics["consensus_errors"] += 1
                    result.warnings.append(
                        "Consensus building failed or returned invalid result"
                    )

            # Завершение
            result.processing_stage = ProcessingStage.COMPLETED
            result.status = PipelineStatus.COMPLETED

            # Сохранение в кэш
            if self.config.cache_enabled:
                self.cache[cache_key] = result
                if len(self.cache) > self.config.cache_max_size:
                    # Удаление старых записей
                    oldest_key = next(iter(self.cache))
                    del self.cache[oldest_key]

            self.metrics["successful_requests"] += 1

        except Exception as e:
            result.status = PipelineStatus.FAILED
            result.processing_stage = ProcessingStage.FAILED
            result.errors.append(str(e))
            self.metrics["failed_requests"] += 1
            self.logger.error(f"Pipeline processing failed for {request.symbol}: {e}")

        finally:
            # Завершение обработки
            result.end_time = datetime.now()
            if result.start_time:
                result.processing_time_seconds = (
                    result.end_time - result.start_time
                ).total_seconds()
                self.metrics["processing_times"].append(result.processing_time_seconds)

        return result

    async def _build_context(self, request: PipelineRequest):
        """Построение контекста"""
        if not self.context_builder:
            return None

        try:
            with create_log_context("build_context", request.symbol):
                # Создание запроса для ContextBuilder
                context_request = {
                    "symbol": request.symbol,
                    "timeframes": request.timeframes,
                    "features_data": request.features_data,
                }
                context_results = await self.context_builder.build_context_batch(
                    [context_request]
                )
                return context_results.get(request.symbol)
        except Exception as e:
            self.logger.error(f"Context building failed for {request.symbol}: {e}")
            return None

    async def _build_triggers(self, request: PipelineRequest):
        """Построение триггеров"""
        if not self.triggers_builder:
            return None

        try:
            with create_log_context("build_triggers", request.symbol):
                # Создание запроса для TriggersBuilder
                triggers_request = {
                    "symbol": request.symbol,
                    "timeframes": request.timeframes,
                    "features_data": request.features_data,
                }
                triggers_results = await self.triggers_builder.build_triggers_batch(
                    [triggers_request]
                )
                return triggers_results[0] if triggers_results else None
        except Exception as e:
            self.logger.error(f"Triggers building failed for {request.symbol}: {e}")
            return None

    async def _build_consensus(
        self, request: PipelineRequest, pipeline_result: PipelineResult
    ):
        """Построение консенсуса"""
        if not self.consensus_builder:
            return None

        try:
            with create_log_context("build_consensus", request.symbol):
                # Преобразуем результаты в словари для consensus
                context_data = None
                triggers_data = None

                if pipeline_result.context_result:
                    context_data = {
                        "symbol": pipeline_result.context_result.symbol,
                        "overall_score": pipeline_result.context_result.overall_score,
                        "dominant_regime": pipeline_result.context_result.dominant_regime,
                        "confidence": pipeline_result.context_result.confidence,
                        "valid": pipeline_result.context_result.valid,
                        "timeframes": pipeline_result.context_result.timeframes,
                    }

                if pipeline_result.triggers_result:
                    triggers_data = {
                        "symbol": pipeline_result.triggers_result.symbol,
                        "overall_p_up": pipeline_result.triggers_result.overall_p_up,
                        "overall_p_down": pipeline_result.triggers_result.overall_p_down,
                        "dominant_acceleration": pipeline_result.triggers_result.dominant_acceleration,
                        "valid": pipeline_result.triggers_result.valid,
                        "timeframes": pipeline_result.triggers_result.timeframes,
                    }

                return await self.consensus_builder.build_consensus(
                    symbol=request.symbol,
                    timeframes=request.timeframes,
                    context_data=context_data,
                    triggers_data=triggers_data,
                )
        except Exception as e:
            self.logger.error(f"Consensus building failed for {request.symbol}: {e}")
            return None

    def _generate_cache_key(self, request: PipelineRequest) -> str:
        """Генерация ключа кэша"""
        key_parts = [
            request.symbol,
            ",".join(sorted(request.timeframes)),
            str(hash(str(request.features_data))),
        ]
        return "|".join(key_parts)

    def _are_components_initialized(self) -> bool:
        """Проверка инициализации компонентов"""
        if self.config.context_enabled and not self.context_builder:
            return False
        if self.config.triggers_enabled and not self.triggers_builder:
            return False
        if self.config.consensus_enabled and not self.consensus_builder:
            return False
        return True

    def get_metrics(self) -> PipelineMetrics:
        """Получение метрик"""
        processing_times = self.metrics["processing_times"]
        context_times = self.metrics["context_times"]
        triggers_times = self.metrics["triggers_times"]
        consensus_times = self.metrics["consensus_times"]

        total_requests = self.metrics["total_requests"]
        successful_requests = self.metrics["successful_requests"]
        failed_requests = self.metrics["failed_requests"]

        return PipelineMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            cancelled_requests=self.metrics["cancelled_requests"],
            avg_processing_time=(
                sum(processing_times) / len(processing_times)
                if processing_times
                else 0.0
            ),
            min_processing_time=min(processing_times) if processing_times else 0.0,
            max_processing_time=max(processing_times) if processing_times else 0.0,
            context_build_time=(
                sum(context_times) / len(context_times) if context_times else 0.0
            ),
            triggers_build_time=(
                sum(triggers_times) / len(triggers_times) if triggers_times else 0.0
            ),
            consensus_build_time=(
                sum(consensus_times) / len(consensus_times) if consensus_times else 0.0
            ),
            context_success_rate=self.metrics["context_successes"]
            / max(total_requests, 1),
            triggers_success_rate=self.metrics["triggers_successes"]
            / max(total_requests, 1),
            consensus_success_rate=self.metrics["consensus_successes"]
            / max(total_requests, 1),
            symbols_processed=len(self.metrics["symbols_processed"]),
            unique_symbols=len(self.metrics["symbols_processed"]),
            timeframes_processed=self.metrics["timeframes_processed"],
            avg_timeframes_per_request=self.metrics["timeframes_processed"]
            / max(total_requests, 1),
            total_errors=self.metrics["context_errors"]
            + self.metrics["triggers_errors"]
            + self.metrics["consensus_errors"],
            context_errors=self.metrics["context_errors"],
            triggers_errors=self.metrics["triggers_errors"],
            consensus_errors=self.metrics["consensus_errors"],
            cache_hits=self.metrics["cache_hits"],
            cache_misses=self.metrics["cache_misses"],
            cache_hit_rate=self.metrics["cache_hits"]
            / max(self.metrics["cache_hits"] + self.metrics["cache_misses"], 1),
        )

    def clear_cache(self) -> None:
        """Очистка кэша"""
        self.cache.clear()
        self.logger.info("Pipeline cache cleared")

    def health_check(self) -> dict[str, Any]:
        """Проверка здоровья системы"""
        return {
            "status": "healthy",
            "components_initialized": self._are_components_initialized(),
            "context_enabled": self.config.context_enabled,
            "triggers_enabled": self.config.triggers_enabled,
            "consensus_enabled": self.config.consensus_enabled,
            "cache_enabled": self.config.cache_enabled,
            "cache_size": len(self.cache),
            "total_requests": self.metrics["total_requests"],
            "success_rate": self.metrics["successful_requests"]
            / max(self.metrics["total_requests"], 1),
        }
