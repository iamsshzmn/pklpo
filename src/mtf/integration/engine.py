"""
Core integration engine for MTF system
"""

import uuid
from datetime import datetime
from typing import Any

from ..logging_config import get_integration_logger
from ..pipeline.builder import PipelineBuilder
from .database_client import DatabaseClient
from .models import (
    DataSource,
    IntegrationConfig,
    IntegrationMetrics,
    IntegrationRequest,
    IntegrationResult,
    IntegrationStatus,
    NotificationType,
)
from .notification_client import NotificationClient
from .okx_client import OKXClient


class IntegrationEngine:
    """Движок интеграции с внешними системами"""

    def __init__(self, config: IntegrationConfig):
        self.config = config
        self.logger = get_integration_logger()

        # Инициализация клиентов
        self.okx_client = None
        self.database_client = None
        self.notification_client = None
        self.pipeline_builder = None

        # Метрики
        self.metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cancelled_requests": 0,
            "processing_times": [],
            "okx_api_calls": 0,
            "database_operations": 0,
            "notifications_sent": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "symbols_processed": set(),
            "timeframes_processed": 0,
            "okx_errors": 0,
            "database_errors": 0,
            "notification_errors": 0,
        }

        # Кэш результатов
        self.cache: dict[str, IntegrationResult] = {}

        self.logger.info("IntegrationEngine initialized")

    async def initialize_components(self) -> None:
        """Инициализация компонентов"""
        try:
            # Инициализация OKX клиента
            if self.config.okx_enabled and self.config.okx_api_key:
                self.okx_client = OKXClient(
                    api_key=self.config.okx_api_key,
                    secret_key=self.config.okx_secret_key,
                    passphrase=self.config.okx_passphrase,
                    sandbox=self.config.okx_sandbox,
                )
                self.logger.info("OKX client initialized")

            # Инициализация клиента базы данных
            if self.config.database_enabled and self.config.database_url:
                self.database_client = DatabaseClient(
                    database_url=self.config.database_url,
                    pool_size=self.config.database_pool_size,
                    timeout=self.config.database_timeout,
                )
                # Создание таблиц
                await self.database_client.create_tables()
                self.logger.info("Database client initialized")

            # Инициализация клиента уведомлений
            if self.config.notifications_enabled:
                notification_config = {
                    "slack_webhook_url": self.config.slack_webhook_url,
                    "email_smtp_server": self.config.email_smtp_server,
                    "email_smtp_port": self.config.email_smtp_port,
                    "email_username": self.config.email_username,
                    "email_password": self.config.email_password,
                    "email_from": self.config.email_from,
                    "email_to": self.config.email_to,
                }
                self.notification_client = NotificationClient(notification_config)
                self.logger.info("Notification client initialized")

            # Инициализация pipeline builder
            self.pipeline_builder = PipelineBuilder()
            await self.pipeline_builder.initialize()
            self.logger.info("Pipeline builder initialized")

            self.logger.info("All integration components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize integration components: {e}")
            raise

    async def process_request(self, request: IntegrationRequest) -> IntegrationResult:
        """Обработка запроса интеграции"""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = datetime.now()

        result = IntegrationResult(
            request_id=request_id,
            symbol=request.symbol,
            timeframes=request.timeframes,
            status=IntegrationStatus.PENDING,
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

            result.status = IntegrationStatus.RUNNING

            # Этап 1: Получение рыночных данных
            if DataSource.OKX_API in request.data_sources and self.okx_client:
                market_data = await self._fetch_market_data(request)
                result.market_data = market_data

                if market_data is not None and not market_data.empty:
                    self.metrics["okx_api_calls"] += 1
                else:
                    self.metrics["okx_errors"] += 1
                    result.warnings.append("Failed to fetch market data from OKX")

            # Этап 2: Обработка через pipeline
            if self.pipeline_builder and result.market_data is not None:
                pipeline_result = await self._process_pipeline(
                    request, result.market_data
                )
                result.pipeline_result = pipeline_result

                if pipeline_result and pipeline_result.is_successful:
                    self.logger.info(
                        f"Pipeline processing successful for {request.symbol}"
                    )
                else:
                    result.warnings.append(
                        "Pipeline processing failed or returned invalid result"
                    )

            # Этап 3: Сохранение в базу данных
            if DataSource.DATABASE in request.data_sources and self.database_client:
                database_result = await self._save_to_database(request, result)
                result.database_result = database_result

                if database_result:
                    self.metrics["database_operations"] += 1
                else:
                    self.metrics["database_errors"] += 1
                    result.warnings.append("Failed to save data to database")

            # Этап 4: Отправка уведомлений
            if request.notification_types and self.notification_client:
                notification_result = await self._send_notifications(request, result)
                result.notification_result = notification_result

                if notification_result:
                    self.metrics["notifications_sent"] += 1
                else:
                    self.metrics["notification_errors"] += 1
                    result.warnings.append("Failed to send notifications")

            # Завершение
            result.status = IntegrationStatus.COMPLETED

            # Сохранение в кэш
            if self.config.cache_enabled:
                self.cache[cache_key] = result
                if len(self.cache) > self.config.cache_max_size:
                    # Удаление старых записей
                    oldest_key = next(iter(self.cache))
                    del self.cache[oldest_key]

            self.metrics["successful_requests"] += 1

        except Exception as e:
            result.status = IntegrationStatus.FAILED
            result.errors.append(str(e))
            self.metrics["failed_requests"] += 1
            self.logger.error(
                f"Integration processing failed for {request.symbol}: {e}"
            )

            # Отправка уведомления об ошибке
            if self.notification_client:
                await self.notification_client.send_error_notification(
                    str(e), {"symbol": request.symbol, "request_id": request_id}
                )

        finally:
            # Завершение обработки
            result.end_time = datetime.now()
            if result.start_time:
                result.processing_time_seconds = (
                    result.end_time - result.start_time
                ).total_seconds()
                self.metrics["processing_times"].append(result.processing_time_seconds)

        return result

    async def _fetch_market_data(
        self, request: IntegrationRequest
    ) -> dict[str, Any] | None:
        """Получение рыночных данных"""
        if not self.okx_client:
            return None

        try:
            async with self.okx_client as client:
                return await client.get_market_data(
                    symbol=request.symbol, timeframes=request.timeframes, limit=100
                )
        except Exception as e:
            self.logger.error(f"Failed to fetch market data for {request.symbol}: {e}")
            return None

    async def _process_pipeline(
        self, request: IntegrationRequest, market_data: dict[str, Any]
    ) -> Any | None:
        """Обработка через pipeline"""
        # Если pipeline_result уже передан, используем его
        if request.pipeline_result:
            return request.pipeline_result

        # Иначе обрабатываем через pipeline
        if not self.pipeline_builder:
            return None

        try:
            return await self.pipeline_builder.process_single(
                symbol=request.symbol,
                timeframes=request.timeframes,
                features_data=market_data,
            )
        except Exception as e:
            self.logger.error(f"Pipeline processing failed for {request.symbol}: {e}")
            return None

    async def _save_to_database(
        self, request: IntegrationRequest, result: IntegrationResult
    ) -> dict[str, Any] | None:
        """Сохранение в базу данных"""
        if not self.database_client:
            return None

        try:
            async with self.database_client as client:
                # Сохранение рыночных данных
                if result.market_data:
                    for timeframe, data in result.market_data.items():
                        await client.save_market_data(request.symbol, timeframe, data)

                # Сохранение результата pipeline
                if result.pipeline_result:
                    await client.save_pipeline_result(result.pipeline_result)

                return {"saved": True}
        except Exception as e:
            self.logger.error(f"Database save failed for {request.symbol}: {e}")
            return None

    async def _send_notifications(
        self, request: IntegrationRequest, result: IntegrationResult
    ) -> dict[str, Any] | None:
        """Отправка уведомлений"""
        if not self.notification_client:
            return None

        try:
            async with self.notification_client as client:
                notification_results = {}

                for notification_type in request.notification_types:
                    if notification_type == NotificationType.SLACK:
                        success = await client.send_slack_notification(
                            f"MTF processing completed for {request.symbol}"
                        )
                        notification_results["slack"] = success

                    elif notification_type == NotificationType.EMAIL:
                        success = await client.send_email_notification(
                            subject=f"MTF Processing - {request.symbol}",
                            message=f"MTF processing completed for {request.symbol}",
                        )
                        notification_results["email"] = success

                return notification_results
        except Exception as e:
            self.logger.error(f"Notification sending failed for {request.symbol}: {e}")
            return None

    def _generate_cache_key(self, request: IntegrationRequest) -> str:
        """Генерация ключа кэша"""
        # Обработка data_sources - может быть enum или строка
        data_sources_str = []
        for ds in request.data_sources:
            if hasattr(ds, "value"):
                data_sources_str.append(ds.value)
            else:
                data_sources_str.append(str(ds))

        key_parts = [
            request.symbol,
            ",".join(sorted(request.timeframes)),
            ",".join(sorted(data_sources_str)),
        ]
        return "|".join(key_parts)

    def _are_components_initialized(self) -> bool:
        """Проверка инициализации компонентов"""
        if self.config.okx_enabled and not self.okx_client:
            return False
        if self.config.database_enabled and not self.database_client:
            return False
        if self.config.notifications_enabled and not self.notification_client:
            return False
        return self.pipeline_builder

    def get_metrics(self) -> IntegrationMetrics:
        """Получение метрик"""
        processing_times = self.metrics["processing_times"]

        total_requests = self.metrics["total_requests"]
        successful_requests = self.metrics["successful_requests"]
        failed_requests = self.metrics["failed_requests"]

        return IntegrationMetrics(
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
            okx_api_calls=self.metrics["okx_api_calls"],
            database_operations=self.metrics["database_operations"],
            cache_hits=self.metrics["cache_hits"],
            cache_misses=self.metrics["cache_misses"],
            notifications_sent=self.metrics["notifications_sent"],
            symbols_processed=len(self.metrics["symbols_processed"]),
            unique_symbols=len(self.metrics["symbols_processed"]),
            timeframes_processed=self.metrics["timeframes_processed"],
            avg_timeframes_per_request=self.metrics["timeframes_processed"]
            / max(total_requests, 1),
            total_errors=self.metrics["okx_errors"]
            + self.metrics["database_errors"]
            + self.metrics["notification_errors"],
            okx_errors=self.metrics["okx_errors"],
            database_errors=self.metrics["database_errors"],
            notification_errors=self.metrics["notification_errors"],
        )

    def clear_cache(self) -> None:
        """Очистка кэша"""
        self.cache.clear()
        self.logger.info("Integration cache cleared")

    async def health_check(self) -> dict[str, Any]:
        """Проверка здоровья системы"""
        health_status = {
            "status": "healthy",
            "components_initialized": self._are_components_initialized(),
            "okx_enabled": self.config.okx_enabled,
            "database_enabled": self.config.database_enabled,
            "notifications_enabled": self.config.notifications_enabled,
            "cache_enabled": self.config.cache_enabled,
            "cache_size": len(self.cache),
            "total_requests": self.metrics["total_requests"],
            "success_rate": self.metrics["successful_requests"]
            / max(self.metrics["total_requests"], 1),
        }

        # Проверка здоровья компонентов
        if self.okx_client:
            try:
                async with self.okx_client as client:
                    okx_health = await client.health_check()
                    health_status["okx_health"] = okx_health
            except Exception as e:
                health_status["okx_health"] = {"status": "unhealthy", "error": str(e)}

        if self.database_client:
            try:
                async with self.database_client as client:
                    db_health = await client.health_check()
                    health_status["database_health"] = db_health
            except Exception as e:
                health_status["database_health"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        if self.notification_client:
            try:
                async with self.notification_client as client:
                    notification_health = await client.health_check()
                    health_status["notification_health"] = notification_health
            except Exception as e:
                health_status["notification_health"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return health_status
