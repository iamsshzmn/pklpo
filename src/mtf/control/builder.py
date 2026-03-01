"""
Main builder interface for MTF Control module
"""

import asyncio
import uuid
from typing import Any

from ..logging_config import get_control_logger
from .config import ControlConfigManager
from .engine import ControlEngine
from .models import (
    ControlAction,
    ControlConfig,
    ControlRequest,
    ControlResult,
    SystemStatus,
)


class ControlBuilder:
    """Главный интерфейс для управления MTF системой"""

    def __init__(self, config: ControlConfig | None = None):
        self.logger = get_control_logger()

        # Инициализация конфигурации
        self.config_manager = ControlConfigManager()
        self.config = config or self.config_manager.get_config()

        # Инициализация движка
        self.engine = ControlEngine(self.config)

        self.logger.info(
            f"ControlBuilder initialized with config: {self.config.to_dict()}"
        )

    async def initialize(self) -> None:
        """Инициализация системы управления"""
        try:
            self.logger.info("Initializing control system...")
            # Движок уже инициализирован в конструкторе
            self.logger.info("Control system initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize control system: {e}")
            raise

    async def start_system(self) -> ControlResult:
        """Запуск системы"""
        return await self.engine.start_system()

    async def stop_system(self) -> ControlResult:
        """Остановка системы"""
        return await self.engine.stop_system()

    async def restart_system(self) -> ControlResult:
        """Перезапуск системы"""
        return await self.engine.restart_system()

    async def get_system_status(self) -> ControlResult:
        """Получение статуса системы"""
        return await self.engine.get_system_status()

    async def health_check(self) -> ControlResult:
        """Проверка здоровья системы"""
        return await self.engine.health_check()

    async def get_metrics(self) -> ControlResult:
        """Получение метрик системы"""
        return await self.engine._handle_metrics(
            ControlRequest(action=ControlAction.METRICS, request_id=str(uuid.uuid4()))
        )

    async def configure_system(self, config_updates: dict[str, Any]) -> ControlResult:
        """Конфигурация системы"""
        request = ControlRequest(
            action=ControlAction.CONFIGURE,
            parameters={"config": config_updates},
            request_id=str(uuid.uuid4()),
        )

        return await self.engine.process_request(request)

    async def process_request(self, request: ControlRequest) -> ControlResult:
        """Обработка запроса управления"""
        return await self.engine.process_request(request)

    def get_system_state(self) -> dict[str, Any]:
        """Получение состояния системы"""
        return {
            "status": self.engine.system_state.status.value,
            "uptime_seconds": self.engine.system_state.uptime_seconds,
            "components": {
                k: v.value for k, v in self.engine.system_state.components.items()
            },
            "memory_usage_mb": self.engine.system_state.memory_usage_mb,
            "cpu_usage_percent": self.engine.system_state.cpu_usage_percent,
            "total_requests": self.engine.system_state.total_requests,
            "successful_requests": self.engine.system_state.successful_requests,
            "failed_requests": self.engine.system_state.failed_requests,
            "success_rate": self.engine.system_state.success_rate,
            "is_healthy": self.engine.system_state.is_healthy,
            "error_count": self.engine.system_state.error_count,
            "last_error": self.engine.system_state.last_error,
        }

    def get_component_status(self) -> dict[str, str]:
        """Получение статуса компонентов"""
        return {k: v.value for k, v in self.engine.system_state.components.items()}

    def is_system_running(self) -> bool:
        """Проверка, запущена ли система"""
        return self.engine.system_state.status == SystemStatus.RUNNING

    def is_system_healthy(self) -> bool:
        """Проверка, здорова ли система"""
        return self.engine.system_state.is_healthy

    def get_config(self) -> ControlConfig:
        """Получение текущей конфигурации"""
        return self.config

    def update_config(self, updates: dict[str, Any]) -> None:
        """Обновление конфигурации"""
        self.config_manager.update_config(updates)
        self.config = self.config_manager.get_config()

        # Обновление конфигурации движка
        self.engine.config = self.config

        self.logger.info(f"Configuration updated: {updates}")

    def get_supported_actions(self) -> list[ControlAction]:
        """Получение поддерживаемых действий"""
        return [
            ControlAction.START,
            ControlAction.STOP,
            ControlAction.RESTART,
            ControlAction.CONFIGURE,
            ControlAction.STATUS,
            ControlAction.HEALTH_CHECK,
            ControlAction.METRICS,
        ]

    def get_supported_components(self) -> list[str]:
        """Получение поддерживаемых компонентов"""
        return ["context", "triggers", "consensus", "pipeline", "integration"]

    def validate_request(self, request: ControlRequest) -> bool:
        """Валидация запроса"""
        if not request.action:
            return False

        if request.action not in self.get_supported_actions():
            return False

        if (
            request.target_component
            and request.target_component not in self.get_supported_components()
        ):
            return False

        return True

    async def process_with_retry(
        self, request: ControlRequest, max_retries: int | None = None
    ) -> ControlResult:
        """Обработка с повторными попытками"""
        max_retries = max_retries or self.config.retry_attempts

        last_result = None

        for attempt in range(max_retries + 1):
            try:
                result = await self.process_request(request)

                if result.success:
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
                    return ControlResult(
                        request_id=request.request_id,
                        action=request.action,
                        success=False,
                        message=f"Max retries exceeded: {e}",
                        errors=[str(e)],
                    )

        return last_result or ControlResult(
            request_id=request.request_id,
            action=request.action,
            success=False,
            message="Max retries exceeded",
            errors=["Max retries exceeded"],
        )

    def get_processing_stats(self) -> dict[str, Any]:
        """Получение статистики обработки"""
        metrics = self.engine.get_metrics()

        return {
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate": metrics.successful_requests
            / max(metrics.total_requests, 1),
            "avg_response_time": metrics.avg_response_time,
            "min_response_time": metrics.min_response_time,
            "max_response_time": metrics.max_response_time,
            "total_errors": metrics.total_errors,
            "component_errors": metrics.component_errors,
            "configuration_errors": metrics.configuration_errors,
            "timeout_errors": metrics.timeout_errors,
            "system_uptime": metrics.system_uptime,
            "components_ready": metrics.components_ready,
            "components_running": metrics.components_running,
            "components_error": metrics.components_error,
        }

    def get_resource_usage(self) -> dict[str, Any]:
        """Получение использования ресурсов"""
        return {
            "memory_usage_mb": self.engine.system_state.memory_usage_mb,
            "cpu_usage_percent": self.engine.system_state.cpu_usage_percent,
            "max_memory_usage_mb": self.config.max_memory_usage_mb,
            "max_cpu_usage_percent": self.config.max_cpu_usage_percent,
            "memory_usage_percent": (
                self.engine.system_state.memory_usage_mb
                / self.config.max_memory_usage_mb
            )
            * 100,
        }

    def get_alert_status(self) -> dict[str, Any]:
        """Получение статуса алертов"""
        return {
            "alerts_enabled": self.config.enable_alerts,
            "error_threshold": self.config.alert_threshold_errors,
            "response_time_threshold": self.config.alert_threshold_response_time,
            "memory_threshold": self.config.alert_threshold_memory_usage,
            "cpu_threshold": self.config.alert_threshold_cpu_usage,
            "current_errors": self.engine.system_state.error_count,
            "current_response_time": self.engine.get_metrics().avg_response_time,
            "current_memory_usage": self.engine.system_state.memory_usage_mb,
            "current_cpu_usage": self.engine.system_state.cpu_usage_percent,
            "alerts_triggered": {
                "high_errors": self.engine.system_state.error_count
                > self.config.alert_threshold_errors,
                "high_response_time": self.engine.get_metrics().avg_response_time
                > self.config.alert_threshold_response_time,
                "high_memory": self.engine.system_state.memory_usage_mb
                > self.config.alert_threshold_memory_usage,
                "high_cpu": self.engine.system_state.cpu_usage_percent
                > self.config.alert_threshold_cpu_usage,
            },
        }

    def get_monitoring_status(self) -> dict[str, Any]:
        """Получение статуса мониторинга"""
        return {
            "monitoring_enabled": self.config.enable_monitoring,
            "monitoring_interval_seconds": self.config.monitoring_interval_seconds,
            "health_check_interval_seconds": self.config.health_check_interval_seconds,
            "metrics_collection_interval_seconds": self.config.metrics_collection_interval_seconds,
            "monitoring_task_running": self.engine.monitoring_task is not None
            and not self.engine.monitoring_task.done(),
            "auto_recovery_enabled": self.config.enable_auto_recovery,
            "auto_recovery_attempts": self.config.auto_recovery_attempts,
            "auto_recovery_delay_seconds": self.config.auto_recovery_delay_seconds,
        }

    async def cleanup(self) -> None:
        """Очистка ресурсов"""
        try:
            await self.engine.cleanup()
            self.logger.info("Control system cleaned up successfully")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Деструктор"""
        try:
            if hasattr(self, "engine") and self.engine:
                asyncio.create_task(self.cleanup())
        except Exception:
            pass  # Игнорируем ошибки в деструкторе
