"""
Main builder interface for MTF Pipeline module
"""

import asyncio
import uuid
from typing import Any

from ..logging_config import create_log_context, get_pipeline_logger
from .config import PipelineConfigManager
from .engine import PipelineEngine
from .models import (
    PipelineConfig,
    PipelineMetrics,
    PipelineRequest,
    PipelineResult,
    PipelineStatus,
)


class PipelineBuilder:
    """Главный интерфейс для построения pipeline"""

    def __init__(self, config: PipelineConfig | None = None):
        self.logger = get_pipeline_logger()

        # Инициализация конфигурации
        self.config_manager = PipelineConfigManager()
        self.config = config or self.config_manager.get_config()

        # Инициализация движка
        self.engine = PipelineEngine(self.config)

        self.logger.info(
            f"PipelineBuilder initialized with config: {self.config.to_dict()}"
        )

    async def initialize(self) -> None:
        """Инициализация pipeline"""
        try:
            await self.engine.initialize_components()
            self.logger.info("Pipeline initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize pipeline: {e}")
            raise

    async def process_single(
        self,
        symbol: str,
        timeframes: list[str],
        features_data: dict[str, Any],
        request_id: str | None = None,
        **kwargs,
    ) -> PipelineResult:
        """Обработка одного запроса"""
        request = PipelineRequest(
            symbol=symbol,
            timeframes=timeframes,
            features_data=features_data,
            request_id=request_id,
            **kwargs,
        )

        return await self.process_request(request)

    async def process_batch(
        self, requests: list[PipelineRequest], max_concurrent: int | None = None
    ) -> list[PipelineResult]:
        """Обработка пакета запросов"""
        max_concurrent = max_concurrent or self.config.max_workers

        # Создание семафора для ограничения параллельности
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(request: PipelineRequest) -> PipelineResult:
            async with semaphore:
                return await self.process_request(request)

        # Обработка запросов
        tasks = [process_with_semaphore(request) for request in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обработка результатов
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Создание результата с ошибкой
                error_result = PipelineResult(
                    request_id=requests[i].request_id or str(uuid.uuid4()),
                    symbol=requests[i].symbol,
                    timeframes=requests[i].timeframes,
                    status=PipelineStatus.FAILED,
                    errors=[str(result)],
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    async def process_request(self, request: PipelineRequest) -> PipelineResult:
        """Обработка запроса"""
        with create_log_context("process_request", request.symbol):
            return await self.engine.process_request(request)

    def get_metrics(self) -> PipelineMetrics:
        """Получение метрик"""
        return self.engine.get_metrics()

    def health_check(self) -> dict[str, Any]:
        """Проверка здоровья системы"""
        return self.engine.health_check()

    def clear_cache(self) -> None:
        """Очистка кэша"""
        self.engine.clear_cache()

    def update_config(self, updates: dict[str, Any]) -> None:
        """Обновление конфигурации"""
        self.config_manager.update_config(updates)
        self.config = self.config_manager.get_config()

        # Обновление конфигурации движка
        self.engine.config = self.config

        self.logger.info(f"Configuration updated: {updates}")

    def get_config(self) -> PipelineConfig:
        """Получение текущей конфигурации"""
        return self.config

    def get_component_status(self) -> dict[str, Any]:
        """Получение статуса компонентов"""
        return {
            "context": {
                "enabled": self.config.context_enabled,
                "initialized": self.engine.context_builder is not None,
            },
            "triggers": {
                "enabled": self.config.triggers_enabled,
                "initialized": self.engine.triggers_builder is not None,
            },
            "consensus": {
                "enabled": self.config.consensus_enabled,
                "initialized": self.engine.consensus_builder is not None,
            },
        }

    def get_supported_timeframes(self) -> list[str]:
        """Получение поддерживаемых таймфреймов"""
        return ["1m", "5m", "15m", "1H", "4H", "1D"]

    def validate_request(self, request: PipelineRequest) -> bool:
        """Валидация запроса"""
        if not request.symbol:
            return False

        if not request.timeframes:
            return False

        if not request.features_data:
            return False

        return not len(request.timeframes) > self.config.max_timeframes_per_request

    async def process_with_retry(
        self, request: PipelineRequest, max_retries: int | None = None
    ) -> PipelineResult:
        """Обработка с повторными попытками"""
        max_retries = max_retries or self.config.retry_attempts

        last_result = None

        for attempt in range(max_retries + 1):
            try:
                result = await self.process_request(request)

                if result.is_successful:
                    return result

                last_result = result

                if attempt < max_retries:
                    await asyncio.sleep(self.config.retry_delay_seconds)

            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(self.config.retry_delay_seconds)
                else:
                    # Создание результата с ошибкой
                    return PipelineResult(
                        request_id=request.request_id or str(uuid.uuid4()),
                        symbol=request.symbol,
                        timeframes=request.timeframes,
                        status=PipelineStatus.FAILED,
                        errors=[str(e)],
                    )

        return last_result or PipelineResult(
            request_id=request.request_id or str(uuid.uuid4()),
            symbol=request.symbol,
            timeframes=request.timeframes,
            status=PipelineStatus.FAILED,
            errors=["Max retries exceeded"],
        )

    def get_cache_stats(self) -> dict[str, Any]:
        """Получение статистики кэша"""
        return {
            "enabled": self.config.cache_enabled,
            "size": len(self.engine.cache),
            "max_size": self.config.cache_max_size,
            "ttl_seconds": self.config.cache_ttl_seconds,
            "hit_rate": self.engine.get_metrics().cache_hit_rate,
        }

    def get_processing_stats(self) -> dict[str, Any]:
        """Получение статистики обработки"""
        metrics = self.get_metrics()

        return {
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate": metrics.successful_requests
            / max(metrics.total_requests, 1),
            "avg_processing_time": metrics.avg_processing_time,
            "symbols_processed": metrics.symbols_processed,
            "timeframes_processed": metrics.timeframes_processed,
        }
