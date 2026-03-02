"""
Circuit Breaker - автоматическое отключение при превышении порогов

Основные функции:
- Мониторинг ошибок и производительности
- Автоматическое отключение при превышении порогов
- Постепенное восстановление через half-open состояние
- Интеграция с системой уведомлений
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from ..database.client import RiskDatabaseClient
from .models import (
    CircuitBreakerConfig,
    CircuitBreakerState as CBState,
    CircuitBreakerStateData,
    GuardAlert,
    GuardMetrics,
    GuardState,
    GuardStatus,
    GuardType,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit Breaker для автоматического отключения при превышении порогов

    Основные функции:
    - Мониторинг ошибок и производительности
    - Автоматическое отключение при превышении порогов
    - Постепенное восстановление через half-open состояние
    - Интеграция с системой уведомлений
    """

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
        db_client: RiskDatabaseClient | None = None,
    ):
        self.config = config or CircuitBreakerConfig(
            guard_type=GuardType.CIRCUIT_BREAKER, name="default_circuit_breaker"
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._db_client = db_client

        # Состояние circuit breaker
        self.state = CircuitBreakerStateData()

        # Состояние guard
        self.guard_state = GuardState(guard_id=uuid4(), status=GuardStatus.ACTIVE)

        # Метрики
        self.metrics_history: list[GuardMetrics] = []

        # Алерты
        self.alerts: list[GuardAlert] = []

        # Callbacks
        self.on_open_callback: Callable | None = None
        self.on_close_callback: Callable | None = None
        self.on_half_open_callback: Callable | None = None

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнение функции через circuit breaker

        Args:
            func: Функция для выполнения
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции

        Returns:
            Результат выполнения функции

        Raises:
            CircuitBreakerOpenException: Если circuit breaker открыт
        """
        if self.state.state == CBState.OPENED:
            raise CircuitBreakerOpenException("Circuit breaker is open")

        if self.state.state == CBState.HALF_OPEN:
            if self.state.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpenException(
                    "Circuit breaker half-open calls limit exceeded"
                )
            self.state.half_open_calls += 1

        try:
            # Выполняем функцию с таймаутом
            result = self._execute_with_timeout(func, *args, **kwargs)

            # Записываем успех
            self._record_success()

            return result

        except Exception as e:
            # Записываем ошибку
            self._record_failure()

            # Проверяем необходимость открытия
            if self.state.should_open(self.config):
                self._open_circuit()

            raise e

    def _execute_with_timeout(self, func: Callable, *args, **kwargs) -> Any:
        """Выполнение функции с таймаутом"""
        import signal
        import sys

        def timeout_handler(signum, frame):
            raise TimeoutError(
                f"Function execution timeout: {self.config.timeout_sec}s"
            )

        # Устанавливаем таймаут (SIGALRM недоступен на Windows)
        old_handler = None
        alarm_supported = hasattr(signal, "SIGALRM") and sys.platform != "win32"
        if alarm_supported:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.config.timeout_sec)

        try:
            return func(*args, **kwargs)
        finally:
            # Восстанавливаем обработчик, если устанавливали
            if alarm_supported:
                signal.alarm(0)
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)

    def _record_success(self):
        """Запись успешного выполнения"""
        self.state.record_success()
        # metric
        self._log_metric(
            "cb_call_success",
            Decimal("1"),
            {"name": self.config.name, "state": self.state.state.value},
        )

        # Проверяем необходимость закрытия
        if self.state.should_close(self.config):
            self._close_circuit()

        self.logger.debug(
            f"Circuit breaker success recorded: {self.state.success_count}"
        )

    def _record_failure(self):
        """Запись ошибки"""
        self.state.record_failure()
        # metric
        self._log_metric(
            "cb_call_failure",
            Decimal("1"),
            {"name": self.config.name, "state": self.state.state.value},
        )

        self.logger.warning(
            f"Circuit breaker failure recorded: {self.state.failure_count}"
        )

    def _open_circuit(self):
        """Открытие circuit breaker"""
        self.state.state = CBState.OPENED
        self.guard_state.status = GuardStatus.TRIGGERED
        self.guard_state.trigger_count += 1
        self.guard_state.last_triggered = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="circuit_breaker_opened",
            severity="high",
            message=f"Circuit breaker opened: {self.state.failure_count} failures",
            context={
                "failure_count": self.state.failure_count,
                "success_count": self.state.success_count,
                "last_failure": self.state.last_failure,
            },
        )
        self.alerts.append(alert)
        # persist
        self._log_guard_state("opened")
        self._log_alert("circuit_breaker_opened", "high", alert.message, alert.context)

        # Вызываем callback
        if self.on_open_callback:
            self.on_open_callback(self)

        self.logger.warning(
            f"Circuit breaker opened: {self.state.failure_count} failures"
        )

    def _close_circuit(self):
        """Закрытие circuit breaker"""
        self.state.state = CBState.CLOSED
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.last_recovery = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Сбрасываем счетчики
        self.state.failure_count = 0
        self.state.success_count = 0
        self.state.half_open_calls = 0

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="circuit_breaker_closed",
            severity="medium",
            message="Circuit breaker closed: system recovered",
            context={
                "recovery_time": datetime.utcnow(),
                "total_failures": self.state.failure_count,
            },
        )
        self.alerts.append(alert)
        # persist
        self._log_guard_state("closed")
        self._log_alert(
            "circuit_breaker_closed", "medium", alert.message, alert.context
        )

        # Вызываем callback
        if self.on_close_callback:
            self.on_close_callback(self)

        self.logger.info("Circuit breaker closed: system recovered")

    def _half_open_circuit(self):
        """Переход в half-open состояние"""
        self.state.state = CBState.HALF_OPEN
        self.state.half_open_calls = 0

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="circuit_breaker_half_open",
            severity="medium",
            message="Circuit breaker half-open: testing recovery",
            context={
                "half_open_calls": self.state.half_open_calls,
                "max_calls": self.config.half_open_max_calls,
            },
        )
        self.alerts.append(alert)
        # persist
        self._log_guard_state("half_open")
        self._log_alert(
            "circuit_breaker_half_open", "medium", alert.message, alert.context
        )

        # Вызываем callback
        if self.on_half_open_callback:
            self.on_half_open_callback(self)

        self.logger.info("Circuit breaker half-open: testing recovery")

    # --- Persistence helpers ---
    def _fire_and_forget(self, coro: Awaitable[Any] | None) -> None:
        if coro is None:
            return
        try:
            import asyncio

            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            # no running loop
            pass

    def _log_metric(
        self, metric_name: str, metric_value: Decimal, labels: dict[str, Any]
    ) -> None:
        if not self._db_client:
            return

        async def write():
            # ensure guard exists and sync id
            gid = await self._db_client.upsert_guard(
                self.config.name,
                self.config.guard_type.value,
                (
                    "active"
                    if self.guard_state.status == GuardStatus.ACTIVE
                    else "triggered"
                ),
                {"source": "cb"},
            )
            self.guard_state.guard_id = gid
            await self._db_client.add_metric(gid, metric_name, metric_value, labels)

        self._fire_and_forget(write())

    def _log_alert(
        self, alert_type: str, severity: str, message: str, context: dict[str, Any]
    ) -> None:
        if not self._db_client:
            return

        async def write():
            gid = await self._db_client.upsert_guard(
                self.config.name,
                self.config.guard_type.value,
                (
                    "active"
                    if self.guard_state.status == GuardStatus.ACTIVE
                    else "triggered"
                ),
                {"source": "cb"},
            )
            self.guard_state.guard_id = gid
            await self._db_client.add_alert(gid, alert_type, severity, message, context)

        self._fire_and_forget(write())

    def _log_guard_state(self, state: str) -> None:
        if not self._db_client:
            return

        async def write():
            gid = await self._db_client.upsert_guard(
                self.config.name,
                self.config.guard_type.value,
                (
                    "active"
                    if self.guard_state.status == GuardStatus.ACTIVE
                    else "triggered"
                ),
                {"source": "cb"},
            )
            self.guard_state.guard_id = gid
            await self._db_client.add_guard_state(
                gid,
                state,
                self.guard_state.trigger_count,
                {"cb_state": self.state.state.value, "name": self.config.name},
            )

        self._fire_and_forget(write())

    def check_recovery(self):
        """Проверка возможности восстановления"""
        if self.state.should_half_open(self.config):
            self._half_open_circuit()

    def get_status(self) -> dict[str, Any]:
        """Получение статуса circuit breaker"""
        return {
            "state": self.state.state.value,
            "failure_count": self.state.failure_count,
            "success_count": self.state.success_count,
            "half_open_calls": self.state.half_open_calls,
            "last_failure": self.state.last_failure,
            "last_success": self.state.last_success,
            "guard_status": self.guard_state.status.value,
            "trigger_count": self.guard_state.trigger_count,
            "last_triggered": self.guard_state.last_triggered,
            "last_recovery": self.guard_state.last_recovery,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_threshold": self.config.recovery_threshold,
                "timeout_sec": self.config.timeout_sec,
                "half_open_max_calls": self.config.half_open_max_calls,
            },
        }

    def get_metrics(self) -> dict[str, Any]:
        """Получение метрик circuit breaker"""
        if not self.metrics_history:
            return {}

        recent_metrics = self.metrics_history[-10:]  # Последние 10 записей

        return {
            "total_calls": self.state.failure_count + self.state.success_count,
            "failure_rate": (
                self.state.failure_count
                / (self.state.failure_count + self.state.success_count)
                if (self.state.failure_count + self.state.success_count) > 0
                else 0.0
            ),
            "success_rate": (
                self.state.success_count
                / (self.state.failure_count + self.state.success_count)
                if (self.state.failure_count + self.state.success_count) > 0
                else 0.0
            ),
            "current_state": self.state.state.value,
            "recent_metrics": [
                {
                    "timestamp": m.timestamp,
                    "metric_value": float(m.metric_value),
                    "is_triggered": m.is_triggered,
                }
                for m in recent_metrics
            ],
        }

    def update_config(self, **kwargs):
        """Обновление конфигурации"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        self.config.updated_at = datetime.utcnow()
        self.logger.info(f"Updated circuit breaker config: {kwargs}")

    def reset(self):
        """Сброс circuit breaker"""
        self.state = CircuitBreakerStateData()
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.trigger_count = 0
        self.guard_state.last_triggered = None
        self.guard_state.last_recovery = None
        self.guard_state.updated_at = datetime.utcnow()

        self.logger.info("Circuit breaker reset")

    def set_callbacks(
        self,
        on_open: Callable | None = None,
        on_close: Callable | None = None,
        on_half_open: Callable | None = None,
    ):
        """Установка callbacks"""
        self.on_open_callback = on_open
        self.on_close_callback = on_close
        self.on_half_open_callback = on_half_open

        self.logger.info("Circuit breaker callbacks set")

    def get_alerts(self, unacknowledged_only: bool = True) -> list[GuardAlert]:
        """Получение алертов"""
        if unacknowledged_only:
            return [alert for alert in self.alerts if not alert.acknowledged]
        return self.alerts

    def acknowledge_alert(self, alert_id: UUID, acknowledged_by: str):
        """Подтверждение алерта"""
        for alert in self.alerts:
            if alert.guard_id == alert_id:
                alert.acknowledge(acknowledged_by)
                self.logger.info(f"Alert acknowledged by {acknowledged_by}")
                break


class CircuitBreakerOpenException(Exception):
    """Исключение при открытом circuit breaker"""

    pass


class CircuitBreakerManager:
    """
    Менеджер circuit breakers

    Управляет множественными circuit breakers для разных операций
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.circuit_breakers: dict[str, CircuitBreaker] = {}

    def create_circuit_breaker(
        self, name: str, config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Создание circuit breaker"""
        if name in self.circuit_breakers:
            raise ValueError(f"Circuit breaker '{name}' already exists")

        if config is None:
            config = CircuitBreakerConfig(
                guard_type=GuardType.CIRCUIT_BREAKER, name=name
            )

        circuit_breaker = CircuitBreaker(config)
        self.circuit_breakers[name] = circuit_breaker

        self.logger.info(f"Created circuit breaker: {name}")
        return circuit_breaker

    def get_circuit_breaker(self, name: str) -> CircuitBreaker | None:
        """Получение circuit breaker"""
        return self.circuit_breakers.get(name)

    def call_with_circuit_breaker(
        self, name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Выполнение функции через circuit breaker"""
        circuit_breaker = self.get_circuit_breaker(name)
        if circuit_breaker is None:
            raise ValueError(f"Circuit breaker '{name}' not found")

        return circuit_breaker.call(func, *args, **kwargs)

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Получение статуса всех circuit breakers"""
        return {name: cb.get_status() for name, cb in self.circuit_breakers.items()}

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Получение метрик всех circuit breakers"""
        return {name: cb.get_metrics() for name, cb in self.circuit_breakers.items()}

    def reset_all(self):
        """Сброс всех circuit breakers"""
        for cb in self.circuit_breakers.values():
            cb.reset()

        self.logger.info("All circuit breakers reset")

    def check_all_recovery(self):
        """Проверка восстановления всех circuit breakers"""
        for cb in self.circuit_breakers.values():
            cb.check_recovery()
