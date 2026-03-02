"""
Core control engine for MTF system
"""

import asyncio
import contextlib
import uuid
from datetime import datetime
from typing import Any

import psutil

from ..integration.builder import IntegrationBuilder
from ..logging_config import create_log_context, get_control_logger
from ..pipeline.builder import PipelineBuilder
from .models import (
    ComponentStatus,
    ControlAction,
    ControlConfig,
    ControlMetrics,
    ControlRequest,
    ControlResult,
    SystemState,
    SystemStatus,
)


class ControlEngine:
    """Движок управления MTF системой"""

    def __init__(self, config: ControlConfig):
        self.config = config
        self.logger = get_control_logger()

        # Состояние системы
        self.system_state = SystemState(
            status=SystemStatus.STOPPED,
            components={
                "context": ComponentStatus.UNINITIALIZED,
                "triggers": ComponentStatus.UNINITIALIZED,
                "consensus": ComponentStatus.UNINITIALIZED,
                "pipeline": ComponentStatus.UNINITIALIZED,
                "integration": ComponentStatus.UNINITIALIZED,
            },
        )

        # Компоненты системы
        self.pipeline_builder: PipelineBuilder | None = None
        self.integration_builder: IntegrationBuilder | None = None

        # Метрики
        self.metrics: dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "start_actions": 0,
            "stop_actions": 0,
            "restart_actions": 0,
            "configure_actions": 0,
            "status_checks": 0,
            "health_checks": 0,
            "context_operations": 0,
            "triggers_operations": 0,
            "consensus_operations": 0,
            "pipeline_operations": 0,
            "integration_operations": 0,
            "response_times": [],
            "total_errors": 0,
            "component_errors": 0,
            "configuration_errors": 0,
            "timeout_errors": 0,
        }

        # Мониторинг
        self.monitoring_task: asyncio.Task | None = None
        self.start_time: datetime | None = None

        self.logger.info("ControlEngine initialized")

    async def start_system(self) -> ControlResult:
        """Запуск системы"""
        with create_log_context("control_engine", "start_system"):
            request = ControlRequest(
                action=ControlAction.START, request_id=str(uuid.uuid4())
            )

            return await self.process_request(request)

    async def stop_system(self) -> ControlResult:
        """Остановка системы"""
        with create_log_context("control_engine", "stop_system"):
            request = ControlRequest(
                action=ControlAction.STOP, request_id=str(uuid.uuid4())
            )

            return await self.process_request(request)

    async def restart_system(self) -> ControlResult:
        """Перезапуск системы"""
        with create_log_context("control_engine", "restart_system"):
            request = ControlRequest(
                action=ControlAction.RESTART, request_id=str(uuid.uuid4())
            )

            return await self.process_request(request)

    async def get_system_status(self) -> ControlResult:
        """Получение статуса системы"""
        with create_log_context("control_engine", "get_system_status"):
            request = ControlRequest(
                action=ControlAction.STATUS, request_id=str(uuid.uuid4())
            )

            return await self.process_request(request)

    async def health_check(self) -> ControlResult:
        """Проверка здоровья системы"""
        with create_log_context("control_engine", "health_check"):
            request = ControlRequest(
                action=ControlAction.HEALTH_CHECK, request_id=str(uuid.uuid4())
            )

            return await self.process_request(request)

    async def process_request(self, request: ControlRequest) -> ControlResult:
        """Обработка запроса управления"""
        start_time = datetime.now()

        result = ControlResult(
            request_id=request.request_id,
            action=request.action,
            success=False,
            message="",
            start_time=start_time,
        )

        try:
            # Обновление метрик
            self.metrics["total_requests"] += 1

            # Обработка действия
            if request.action == ControlAction.START:
                result = await self._handle_start(request)
            elif request.action == ControlAction.STOP:
                result = await self._handle_stop(request)
            elif request.action == ControlAction.RESTART:
                result = await self._handle_restart(request)
            elif request.action == ControlAction.PAUSE:
                result = await self._handle_pause(request)
            elif request.action == ControlAction.RESUME:
                result = await self._handle_resume(request)
            elif request.action == ControlAction.CONFIGURE:
                result = await self._handle_configure(request)
            elif request.action == ControlAction.STATUS:
                result = await self._handle_status(request)
            elif request.action == ControlAction.HEALTH_CHECK:
                result = await self._handle_health_check(request)
            elif request.action == ControlAction.METRICS:
                result = await self._handle_metrics(request)
            elif request.action == ControlAction.LOGS:
                result = await self._handle_logs(request)
            else:
                result.success = False
                result.message = f"Unknown action: {request.action}"
                result.errors.append(f"Unknown action: {request.action}")

            # Обновление метрик
            if result.success:
                self.metrics["successful_requests"] += 1
            else:
                self.metrics["failed_requests"] += 1
                self.metrics["total_errors"] += 1

        except Exception as e:
            result.success = False
            result.message = f"Error processing request: {e}"
            result.errors.append(str(e))
            self.metrics["failed_requests"] += 1
            self.metrics["total_errors"] += 1
            self.logger.error(f"Error processing control request: {e}")

        finally:
            # Завершение обработки
            result.end_time = datetime.now()
            if result.start_time:
                result.processing_time_seconds = (
                    result.end_time - result.start_time
                ).total_seconds()
                self.metrics["response_times"].append(result.processing_time_seconds)

        return result

    async def _handle_start(self, request: ControlRequest) -> ControlResult:
        """Обработка запуска системы"""
        try:
            self.system_state.status = SystemStatus.STARTING
            self.start_time = datetime.now()

            # Инициализация компонентов
            if self.config.context_enabled:
                self.system_state.components["context"] = ComponentStatus.INITIALIZING

            if self.config.triggers_enabled:
                self.system_state.components["triggers"] = ComponentStatus.INITIALIZING

            if self.config.consensus_enabled:
                self.system_state.components["consensus"] = ComponentStatus.INITIALIZING

            if self.config.pipeline_enabled:
                self.system_state.components["pipeline"] = ComponentStatus.INITIALIZING
                self.pipeline_builder = PipelineBuilder()
                await self.pipeline_builder.initialize()
                self.system_state.components["pipeline"] = ComponentStatus.READY

            if self.config.integration_enabled:
                self.system_state.components["integration"] = (
                    ComponentStatus.INITIALIZING
                )
                self.integration_builder = IntegrationBuilder()
                await self.integration_builder.initialize()
                self.system_state.components["integration"] = ComponentStatus.READY

            # Запуск мониторинга
            if self.config.enable_monitoring:
                self.monitoring_task = asyncio.create_task(self._monitoring_loop())

            self.system_state.status = SystemStatus.RUNNING
            self.metrics["start_actions"] += 1

            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=True,
                message="System started successfully",
                component_results={
                    "system_status": self.system_state.status.value,
                    "components": {
                        k: v.value for k, v in self.system_state.components.items()
                    },
                },
            )

        except Exception as e:
            self.system_state.status = SystemStatus.ERROR
            self.metrics["component_errors"] += 1
            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=False,
                message=f"Failed to start system: {e}",
                errors=[str(e)],
            )

    async def _handle_stop(self, request: ControlRequest) -> ControlResult:
        """Обработка остановки системы"""
        try:
            self.system_state.status = SystemStatus.STOPPING

            # Остановка мониторинга
            if self.monitoring_task:
                self.monitoring_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.monitoring_task
                self.monitoring_task = None

            # Остановка компонентов
            if self.pipeline_builder:
                self.pipeline_builder = None
                self.system_state.components["pipeline"] = ComponentStatus.STOPPED

            if self.integration_builder:
                self.integration_builder = None
                self.system_state.components["integration"] = ComponentStatus.STOPPED

            # Остановка других компонентов
            for component in self.system_state.components:
                if (
                    self.system_state.components[component]
                    != ComponentStatus.UNINITIALIZED
                ):
                    self.system_state.components[component] = ComponentStatus.STOPPED

            self.system_state.status = SystemStatus.STOPPED
            self.metrics["stop_actions"] += 1

            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=True,
                message="System stopped successfully",
                component_results={
                    "system_status": self.system_state.status.value,
                    "components": {
                        k: v.value for k, v in self.system_state.components.items()
                    },
                },
            )

        except Exception as e:
            self.system_state.status = SystemStatus.ERROR
            self.metrics["component_errors"] += 1
            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=False,
                message=f"Failed to stop system: {e}",
                errors=[str(e)],
            )

    async def _handle_restart(self, request: ControlRequest) -> ControlResult:
        """Обработка перезапуска системы"""
        try:
            # Остановка
            stop_result = await self._handle_stop(request)
            if not stop_result.success:
                return stop_result

            # Небольшая задержка
            await asyncio.sleep(1.0)

            # Запуск
            start_result = await self._handle_start(request)
            self.metrics["restart_actions"] += 1

            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=start_result.success,
                message=f"System restart {'successful' if start_result.success else 'failed'}",
                component_results=start_result.component_results,
                errors=start_result.errors,
            )

        except Exception as e:
            self.metrics["component_errors"] += 1
            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=False,
                message=f"Failed to restart system: {e}",
                errors=[str(e)],
            )

    async def _handle_pause(self, request: ControlRequest) -> ControlResult:
        """Обработка паузы системы"""
        # В текущей реализации пауза не поддерживается
        return ControlResult(
            request_id=request.request_id,
            action=request.action,
            success=False,
            message="Pause functionality not implemented",
            errors=["Pause functionality not implemented"],
        )

    async def _handle_resume(self, request: ControlRequest) -> ControlResult:
        """Обработка возобновления системы"""
        # В текущей реализации возобновление не поддерживается
        return ControlResult(
            request_id=request.request_id,
            action=request.action,
            success=False,
            message="Resume functionality not implemented",
            errors=["Resume functionality not implemented"],
        )

    async def _handle_configure(self, request: ControlRequest) -> ControlResult:
        """Обработка конфигурации системы"""
        try:
            # Обновление конфигурации
            if "config" in request.parameters:
                config_updates = request.parameters["config"]
                for key, value in config_updates.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)

            self.metrics["configure_actions"] += 1

            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=True,
                message="Configuration updated successfully",
                component_results={"config": self.config.to_dict()},
            )

        except Exception as e:
            self.metrics["configuration_errors"] += 1
            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=False,
                message=f"Failed to configure system: {e}",
                errors=[str(e)],
            )

    async def _handle_status(self, request: ControlRequest) -> ControlResult:
        """Обработка получения статуса"""
        try:
            # Обновление состояния системы
            await self._update_system_state()

            self.metrics["status_checks"] += 1

            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=True,
                message="System status retrieved successfully",
                component_results={
                    "system_status": self.system_state.status.value,
                    "uptime_seconds": self.system_state.uptime_seconds,
                    "components": {
                        k: v.value for k, v in self.system_state.components.items()
                    },
                    "memory_usage_mb": self.system_state.memory_usage_mb,
                    "cpu_usage_percent": self.system_state.cpu_usage_percent,
                    "total_requests": self.system_state.total_requests,
                    "successful_requests": self.system_state.successful_requests,
                    "failed_requests": self.system_state.failed_requests,
                    "success_rate": self.system_state.success_rate,
                    "is_healthy": self.system_state.is_healthy,
                },
            )

        except Exception as e:
            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=False,
                message=f"Failed to get system status: {e}",
                errors=[str(e)],
            )

    async def _handle_health_check(self, request: ControlRequest) -> ControlResult:
        """Обработка проверки здоровья"""
        try:
            # Обновление состояния системы
            await self._update_system_state()

            # Проверка здоровья компонентов
            health_results = {}
            for component, status in self.system_state.components.items():
                if status == ComponentStatus.READY or status == ComponentStatus.RUNNING:
                    health_results[component] = "healthy"
                elif status == ComponentStatus.ERROR:
                    health_results[component] = "unhealthy"
                else:
                    health_results[component] = "unknown"

            # Проверка здоровья системы
            is_healthy = self.system_state.is_healthy

            self.metrics["health_checks"] += 1

            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=True,
                message=f"Health check {'passed' if is_healthy else 'failed'}",
                component_results={
                    "is_healthy": is_healthy,
                    "system_status": self.system_state.status.value,
                    "components_health": health_results,
                    "memory_usage_mb": self.system_state.memory_usage_mb,
                    "cpu_usage_percent": self.system_state.cpu_usage_percent,
                    "error_count": self.system_state.error_count,
                    "last_error": self.system_state.last_error,
                },
            )

        except Exception as e:
            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=False,
                message=f"Health check failed: {e}",
                errors=[str(e)],
            )

    async def _handle_metrics(self, request: ControlRequest) -> ControlResult:
        """Обработка получения метрик"""
        try:
            # Обновление состояния системы
            await self._update_system_state()

            # Получение метрик
            metrics = self.get_metrics()

            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=True,
                message="Metrics retrieved successfully",
                component_results={
                    "metrics": (
                        metrics.to_dict() if hasattr(metrics, "to_dict") else metrics
                    ),
                    "system_state": {
                        "status": self.system_state.status.value,
                        "uptime_seconds": self.system_state.uptime_seconds,
                        "memory_usage_mb": self.system_state.memory_usage_mb,
                        "cpu_usage_percent": self.system_state.cpu_usage_percent,
                    },
                },
            )

        except Exception as e:
            return ControlResult(
                request_id=request.request_id,
                action=request.action,
                success=False,
                message=f"Failed to get metrics: {e}",
                errors=[str(e)],
            )

    async def _handle_logs(self, request: ControlRequest) -> ControlResult:
        """Обработка получения логов"""
        # В текущей реализации получение логов не поддерживается
        return ControlResult(
            request_id=request.request_id,
            action=request.action,
            success=False,
            message="Logs functionality not implemented",
            errors=["Logs functionality not implemented"],
        )

    async def _update_system_state(self) -> None:
        """Обновление состояния системы"""
        try:
            # Обновление времени работы
            if self.start_time:
                self.system_state.uptime_seconds = (
                    datetime.now() - self.start_time
                ).total_seconds()

            # Обновление использования ресурсов
            process = psutil.Process()
            self.system_state.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            self.system_state.cpu_usage_percent = process.cpu_percent()

            # Обновление метрик
            self.system_state.total_requests = self.metrics["total_requests"]
            self.system_state.successful_requests = self.metrics["successful_requests"]
            self.system_state.failed_requests = self.metrics["failed_requests"]

            # Обновление ошибок
            self.system_state.error_count = self.metrics["total_errors"]

        except Exception as e:
            self.logger.error(f"Failed to update system state: {e}")

    async def _monitoring_loop(self) -> None:
        """Цикл мониторинга"""
        while True:
            try:
                # Обновление состояния системы
                await self._update_system_state()

                # Проверка алертов
                if self.config.enable_alerts:
                    await self._check_alerts()

                # Ожидание следующей итерации
                await asyncio.sleep(self.config.monitoring_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5.0)  # Короткая пауза при ошибке

    async def _check_alerts(self) -> None:
        """Проверка алертов"""
        try:
            # Проверка ошибок
            if self.metrics["total_errors"] > self.config.alert_threshold_errors:
                self.logger.warning(f"High error count: {self.metrics['total_errors']}")

            # Проверка времени ответа
            if self.metrics["response_times"]:
                avg_response_time = sum(self.metrics["response_times"]) / len(
                    self.metrics["response_times"]
                )
                if avg_response_time > self.config.alert_threshold_response_time:
                    self.logger.warning(f"High response time: {avg_response_time:.2f}s")

            # Проверка использования памяти
            if (
                self.system_state.memory_usage_mb
                > self.config.alert_threshold_memory_usage
            ):
                self.logger.warning(
                    f"High memory usage: {self.system_state.memory_usage_mb:.2f}MB"
                )

            # Проверка использования CPU
            if (
                self.system_state.cpu_usage_percent
                > self.config.alert_threshold_cpu_usage
            ):
                self.logger.warning(
                    f"High CPU usage: {self.system_state.cpu_usage_percent:.2f}%"
                )

        except Exception as e:
            self.logger.error(f"Error checking alerts: {e}")

    def get_metrics(self) -> ControlMetrics:
        """Получение метрик"""
        response_times = self.metrics["response_times"]

        return ControlMetrics(
            total_requests=self.metrics["total_requests"],
            successful_requests=self.metrics["successful_requests"],
            failed_requests=self.metrics["failed_requests"],
            start_actions=self.metrics["start_actions"],
            stop_actions=self.metrics["stop_actions"],
            restart_actions=self.metrics["restart_actions"],
            configure_actions=self.metrics["configure_actions"],
            status_checks=self.metrics["status_checks"],
            health_checks=self.metrics["health_checks"],
            context_operations=self.metrics["context_operations"],
            triggers_operations=self.metrics["triggers_operations"],
            consensus_operations=self.metrics["consensus_operations"],
            pipeline_operations=self.metrics["pipeline_operations"],
            integration_operations=self.metrics["integration_operations"],
            avg_response_time=(
                sum(response_times) / len(response_times) if response_times else 0.0
            ),
            min_response_time=min(response_times) if response_times else 0.0,
            max_response_time=max(response_times) if response_times else 0.0,
            total_errors=self.metrics["total_errors"],
            component_errors=self.metrics["component_errors"],
            configuration_errors=self.metrics["configuration_errors"],
            timeout_errors=self.metrics["timeout_errors"],
            system_uptime=self.system_state.uptime_seconds,
            components_ready=sum(
                1
                for status in self.system_state.components.values()
                if status == ComponentStatus.READY
            ),
            components_running=sum(
                1
                for status in self.system_state.components.values()
                if status == ComponentStatus.RUNNING
            ),
            components_error=sum(
                1
                for status in self.system_state.components.values()
                if status == ComponentStatus.ERROR
            ),
        )

    async def cleanup(self) -> None:
        """Очистка ресурсов"""
        try:
            # Остановка мониторинга
            if self.monitoring_task:
                self.monitoring_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.monitoring_task

            # Остановка компонентов
            if self.pipeline_builder:
                self.pipeline_builder = None

            if self.integration_builder:
                self.integration_builder = None

            self.system_state.status = SystemStatus.STOPPED

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
