"""
Main builder interface for MTF Integration module
"""

import asyncio
import uuid
from typing import Any

from ..logging_config import create_log_context, get_integration_logger
from .config import IntegrationConfigManager
from .engine import IntegrationEngine
from .models import (
    DataSource,
    IntegrationConfig,
    IntegrationMetrics,
    IntegrationRequest,
    IntegrationResult,
    IntegrationStatus,
    NotificationType,
)


class IntegrationBuilder:
    """Главный интерфейс для интеграции с внешними системами"""

    def __init__(self, config: IntegrationConfig | None = None):
        self.logger = get_integration_logger()

        # Инициализация конфигурации
        self.config_manager = IntegrationConfigManager()
        self.config = config or self.config_manager.get_config()

        # Инициализация движка
        self.engine = IntegrationEngine(self.config)

        self.logger.info(
            f"IntegrationBuilder initialized with config: {self.config.to_dict()}"
        )

    async def initialize(self) -> None:
        """Инициализация интеграции"""
        try:
            await self.engine.initialize_components()
            self.logger.info("Integration initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize integration: {e}")
            raise

    async def process_single(
        self,
        symbol: str,
        timeframes: list[str],
        data_sources: list[DataSource],
        notification_types: list[NotificationType] | None = None,
        request_id: str | None = None,
        pipeline_result: Any | None = None,
        **kwargs,
    ) -> IntegrationResult:
        """Обработка одного запроса интеграции"""
        request = IntegrationRequest(
            symbol=symbol,
            timeframes=timeframes,
            data_sources=data_sources,
            notification_types=notification_types or [],
            request_id=request_id,
            pipeline_result=pipeline_result,
            **kwargs,
        )

        return await self.process_request(request)

    async def process_batch(
        self, requests: list[IntegrationRequest], max_concurrent: int | None = None
    ) -> list[IntegrationResult]:
        """Обработка пакета запросов"""
        max_concurrent = max_concurrent or self.config.max_workers

        # Создание семафора для ограничения параллельности
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(
            request: IntegrationRequest,
        ) -> IntegrationResult:
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
                error_result = IntegrationResult(
                    request_id=requests[i].request_id or str(uuid.uuid4()),
                    symbol=requests[i].symbol,
                    timeframes=requests[i].timeframes,
                    status=IntegrationStatus.FAILED,
                    errors=[str(result)],
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    async def process_request(self, request: IntegrationRequest) -> IntegrationResult:
        """Обработка запроса"""
        with create_log_context("process_request", request.symbol):
            return await self.engine.process_request(request)

    async def fetch_market_data(
        self, symbol: str, timeframes: list[str], limit: int = 100
    ) -> dict[str, Any]:
        """Получение рыночных данных из OKX"""
        if not self.engine.okx_client:
            raise Exception("OKX client not initialized")

        try:
            async with self.engine.okx_client as client:
                return await client.get_market_data(symbol, timeframes, limit)
        except Exception as e:
            self.logger.error(f"Failed to fetch market data for {symbol}: {e}")
            raise

    async def save_to_database(self, data: dict[str, Any]) -> bool:
        """Сохранение данных в базу данных"""
        if not self.engine.database_client:
            raise Exception("Database client not initialized")

        try:
            async with self.engine.database_client as client:
                # Сохранение рыночных данных
                if "market_data" in data:
                    for symbol, timeframes_data in data["market_data"].items():
                        for timeframe, df in timeframes_data.items():
                            await client.save_market_data(symbol, timeframe, df)

                # Сохранение результата pipeline
                if "pipeline_result" in data:
                    await client.save_pipeline_result(data["pipeline_result"])

                return True
        except Exception as e:
            self.logger.error(f"Failed to save data to database: {e}")
            return False

    async def send_notification(
        self, notification_type: NotificationType, message: str, **kwargs
    ) -> bool:
        """Отправка уведомления"""
        if not self.engine.notification_client:
            raise Exception("Notification client not initialized")

        try:
            async with self.engine.notification_client as client:
                return await client.send_notification(
                    notification_type, message=message, **kwargs
                )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            return False

    def get_metrics(self) -> IntegrationMetrics:
        """Получение метрик"""
        return self.engine.get_metrics()

    async def health_check(self) -> dict[str, Any]:
        """Проверка здоровья системы"""
        return await self.engine.health_check()

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

    def get_config(self) -> IntegrationConfig:
        """Получение текущей конфигурации"""
        return self.config

    def get_component_status(self) -> dict[str, Any]:
        """Получение статуса компонентов"""
        return {
            "okx": {
                "enabled": self.config.okx_enabled,
                "initialized": self.engine.okx_client is not None,
            },
            "database": {
                "enabled": self.config.database_enabled,
                "initialized": self.engine.database_client is not None,
            },
            "notifications": {
                "enabled": self.config.notifications_enabled,
                "initialized": self.engine.notification_client is not None,
            },
            "pipeline": {"initialized": self.engine.pipeline_builder is not None},
        }

    def get_supported_data_sources(self) -> list[DataSource]:
        """Получение поддерживаемых источников данных"""
        sources = []
        if self.config.okx_enabled:
            sources.append(DataSource.OKX_API)
        if self.config.database_enabled:
            sources.append(DataSource.DATABASE)
        sources.append(DataSource.CACHE)
        return sources

    def get_supported_notification_types(self) -> list[NotificationType]:
        """Получение поддерживаемых типов уведомлений"""
        types = [NotificationType.LOG]  # Лог всегда доступен

        if self.config.notifications_enabled:
            if self.config.slack_webhook_url:
                types.append(NotificationType.SLACK)
            if self.config.email_smtp_server:
                types.append(NotificationType.EMAIL)
            types.append(NotificationType.WEBHOOK)

        return types

    def validate_request(self, request: IntegrationRequest) -> bool:
        """Валидация запроса"""
        if not request.symbol:
            return False

        if not request.timeframes:
            return False

        if not request.data_sources:
            return False

        return not len(request.timeframes) > self.config.max_timeframes_per_request

    async def process_with_retry(
        self, request: IntegrationRequest, max_retries: int | None = None
    ) -> IntegrationResult:
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
                    return IntegrationResult(
                        request_id=request.request_id or str(uuid.uuid4()),
                        symbol=request.symbol,
                        timeframes=request.timeframes,
                        status=IntegrationStatus.FAILED,
                        errors=[str(e)],
                    )

        return last_result or IntegrationResult(
            request_id=request.request_id or str(uuid.uuid4()),
            symbol=request.symbol,
            timeframes=request.timeframes,
            status=IntegrationStatus.FAILED,
            errors=["Max retries exceeded"],
        )

    def get_cache_stats(self) -> dict[str, Any]:
        """Получение статистики кэша"""
        return {
            "enabled": self.config.cache_enabled,
            "size": len(self.engine.cache),
            "max_size": self.config.cache_max_size,
            "ttl_seconds": self.config.cache_ttl_seconds,
            "hit_rate": self.engine.get_metrics().cache_hits
            / max(
                self.engine.get_metrics().cache_hits
                + self.engine.get_metrics().cache_misses,
                1,
            ),
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
            "okx_api_calls": metrics.okx_api_calls,
            "database_operations": metrics.database_operations,
            "notifications_sent": metrics.notifications_sent,
        }
