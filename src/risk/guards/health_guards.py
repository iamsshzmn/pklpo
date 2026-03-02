"""
Health Guard - мониторинг здоровья системы

Основные функции:
- Мониторинг использования ресурсов (CPU, память, диск)
- Контроль количества соединений
- Проверка доступности сервисов
- Блокировка операций при проблемах со здоровьем
"""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psutil

from .models import (
    GuardAlert,
    GuardMetrics,
    GuardState,
    GuardStatus,
    GuardType,
    HealthGuardConfig,
)

logger = logging.getLogger(__name__)


class HealthGuard:
    """
    Health Guard для мониторинга здоровья системы

    Основные функции:
    - Мониторинг использования ресурсов (CPU, память, диск)
    - Контроль количества соединений
    - Проверка доступности сервисов
    - Блокировка операций при проблемах со здоровьем
    """

    def __init__(self, config: HealthGuardConfig | None = None):
        self.config = config or HealthGuardConfig(
            guard_type=GuardType.HEALTH_GUARD, name="default_health_guard"
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние guard
        self.guard_state = GuardState(guard_id=uuid4(), status=GuardStatus.ACTIVE)

        # Метрики
        self.metrics_history: list[GuardMetrics] = []

        # Алерты
        self.alerts: list[GuardAlert] = []

        # История здоровья системы
        self.health_history: list[dict[str, Any]] = []

        # Callbacks
        self.on_trigger_callback: Callable | None = None
        self.on_recovery_callback: Callable | None = None

    def check_system_health(self) -> tuple[bool, list[str]]:
        """
        Проверка здоровья системы

        Returns:
            (здоровье_хорошее, список_проблем)
        """
        problems = []

        try:
            # Проверяем использование ресурсов
            resource_ok, resource_problems = self._check_resource_usage()
            if not resource_ok:
                problems.extend(resource_problems)

            # Проверяем соединения
            connection_ok, connection_problems = self._check_connections()
            if not connection_ok:
                problems.extend(connection_problems)

            # Проверяем доступность сервисов
            service_ok, service_problems = self._check_service_availability()
            if not service_ok:
                problems.extend(service_problems)

            # Записываем состояние здоровья
            health_record = {
                "timestamp": datetime.utcnow(),
                "resource_usage": self._get_resource_usage(),
                "connections": self._get_connection_count(),
                "services": self._get_service_status(),
                "problems": problems.copy(),
            }

            self.health_history.append(health_record)

            # Ограничиваем размер истории
            max_history = 100
            if len(self.health_history) > max_history:
                self.health_history = self.health_history[-max_history:]

            # Обновляем метрики
            self._update_metrics(health_record, len(problems) == 0)

            # Проверяем необходимость срабатывания
            if problems and self.guard_state.should_trigger(self.config):
                self._trigger_guard(problems)

            return len(problems) == 0, problems

        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
            problems.append(f"Health check failed: {e!s}")
            return False, problems

    def _check_resource_usage(self) -> tuple[bool, list[str]]:
        """Проверка использования ресурсов"""
        problems = []

        try:
            # Проверяем CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.config.cpu_threshold * 100:
                problems.append(
                    f"CPU usage too high: {cpu_percent:.1f}% > {self.config.cpu_threshold * 100:.1f}%"
                )

            # Проверяем память
            memory = psutil.virtual_memory()
            memory_percent = memory.percent / 100
            if memory_percent > self.config.memory_threshold:
                problems.append(
                    f"Memory usage too high: {memory.percent:.1f}% > {self.config.memory_threshold * 100:.1f}%"
                )

            # Проверяем диск
            disk = psutil.disk_usage("/")
            disk_percent = disk.percent / 100
            if disk_percent > self.config.disk_threshold:
                problems.append(
                    f"Disk usage too high: {disk.percent:.1f}% > {self.config.disk_threshold * 100:.1f}%"
                )

            return len(problems) == 0, problems

        except Exception as e:
            self.logger.error(f"Error checking resource usage: {e}")
            return False, [f"Resource check failed: {e!s}"]

    def _check_connections(self) -> tuple[bool, list[str]]:
        """Проверка соединений"""
        problems = []

        try:
            # Получаем количество соединений
            connections = psutil.net_connections()
            connection_count = len(connections)

            if connection_count > self.config.connection_threshold:
                problems.append(
                    f"Too many connections: {connection_count} > {self.config.connection_threshold}"
                )

            return len(problems) == 0, problems

        except Exception as e:
            self.logger.error(f"Error checking connections: {e}")
            return False, [f"Connection check failed: {e!s}"]

    def _check_service_availability(self) -> tuple[bool, list[str]]:
        """Проверка доступности сервисов"""
        problems = []

        try:
            # Здесь можно добавить проверку доступности конкретных сервисов
            # Пока просто возвращаем успех
            return True, problems

        except Exception as e:
            self.logger.error(f"Error checking service availability: {e}")
            return False, [f"Service check failed: {e!s}"]

    def _get_resource_usage(self) -> dict[str, Any]:
        """Получение информации об использовании ресурсов"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3),
            }
        except Exception as e:
            self.logger.error(f"Error getting resource usage: {e}")
            return {}

    def _get_connection_count(self) -> int:
        """Получение количества соединений"""
        try:
            connections = psutil.net_connections()
            return len(connections)
        except Exception as e:
            self.logger.error(f"Error getting connection count: {e}")
            return 0

    def _get_service_status(self) -> dict[str, Any]:
        """Получение статуса сервисов"""
        # Здесь можно добавить проверку статуса конкретных сервисов
        return {"status": "unknown"}

    def _update_metrics(self, health_record: dict[str, Any], is_health_good: bool):
        """Обновление метрик"""
        # Рассчитываем health score
        health_score = 1.0 if is_health_good else 0.0

        # Создаем метрику
        metric = GuardMetrics(
            guard_id=self.guard_state.guard_id,
            metric_value=Decimal(str(health_score)),
            threshold_value=self.config.threshold,
            is_triggered=not is_health_good,
            trigger_count=self.guard_state.trigger_count,
            context={"health_record": health_record, "health_score": health_score},
        )

        self.metrics_history.append(metric)

        # Ограничиваем размер истории метрик
        max_metrics = 1000
        if len(self.metrics_history) > max_metrics:
            self.metrics_history = self.metrics_history[-max_metrics:]

    def _trigger_guard(self, problems: list[str]):
        """Срабатывание guard"""
        self.guard_state.status = GuardStatus.TRIGGERED
        self.guard_state.trigger_count += 1
        self.guard_state.last_triggered = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="health_guard_triggered",
            severity="high",
            message=f"System health issues detected: {len(problems)} problems",
            context={
                "problems": problems,
                "trigger_count": self.guard_state.trigger_count,
                "threshold": float(self.config.threshold),
            },
        )
        self.alerts.append(alert)

        # Вызываем callback
        if self.on_trigger_callback:
            self.on_trigger_callback(self, problems)

        self.logger.warning(
            f"Health Guard triggered: {len(problems)} system health issues"
        )

    def check_recovery(self):
        """Проверка восстановления"""
        if self.guard_state.can_recover(self.config):
            self._recover_guard()

    def _recover_guard(self):
        """Восстановление guard"""
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.last_recovery = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="health_guard_recovered",
            severity="medium",
            message="Health guard recovered",
            context={
                "recovery_time": datetime.utcnow(),
                "total_triggers": self.guard_state.trigger_count,
            },
        )
        self.alerts.append(alert)

        # Вызываем callback
        if self.on_recovery_callback:
            self.on_recovery_callback(self)

        self.logger.info("Health Guard recovered")

    def get_status(self) -> dict[str, Any]:
        """Получение статуса health guard"""
        return {
            "status": self.guard_state.status.value,
            "is_triggered": self.guard_state.is_triggered(),
            "trigger_count": self.guard_state.trigger_count,
            "last_triggered": self.guard_state.last_triggered,
            "last_recovery": self.guard_state.last_recovery,
            "health_history_size": len(self.health_history),
            "metrics_history_size": len(self.metrics_history),
            "config": {
                "memory_threshold": float(self.config.memory_threshold),
                "cpu_threshold": float(self.config.cpu_threshold),
                "disk_threshold": float(self.config.disk_threshold),
                "connection_threshold": self.config.connection_threshold,
            },
        }

    def get_metrics(self) -> dict[str, Any]:
        """Получение метрик health guard"""
        if not self.metrics_history:
            return {}

        recent_metrics = self.metrics_history[-10:]  # Последние 10 записей

        # Рассчитываем статистику
        health_scores = [float(m.metric_value) for m in recent_metrics]
        avg_health_score = (
            sum(health_scores) / len(health_scores) if health_scores else 0.0
        )

        return {
            "avg_health_score": avg_health_score,
            "total_checks": len(self.metrics_history),
            "failed_checks": sum(1 for m in self.metrics_history if not m.is_triggered),
            "success_rate": (
                sum(1 for m in self.metrics_history if m.is_triggered)
                / len(self.metrics_history)
                if self.metrics_history
                else 0.0
            ),
            "recent_metrics": [
                {
                    "timestamp": m.timestamp,
                    "health_score": float(m.metric_value),
                    "is_triggered": m.is_triggered,
                }
                for m in recent_metrics
            ],
        }

    def get_health_report(self) -> dict[str, Any]:
        """Получение отчета о здоровье системы"""
        if not self.health_history:
            return {"message": "No health history available"}

        recent_health = self.health_history[-10:]  # Последние 10 записей

        # Анализируем использование ресурсов
        resource_usage = []
        for record in recent_health:
            if "resource_usage" in record:
                resource_usage.append(record["resource_usage"])

        # Рассчитываем средние значения
        if resource_usage:
            avg_cpu = sum(r.get("cpu_percent", 0) for r in resource_usage) / len(
                resource_usage
            )
            avg_memory = sum(r.get("memory_percent", 0) for r in resource_usage) / len(
                resource_usage
            )
            avg_disk = sum(r.get("disk_percent", 0) for r in resource_usage) / len(
                resource_usage
            )
        else:
            avg_cpu = avg_memory = avg_disk = 0.0

        # Анализируем проблемы
        total_problems = sum(
            len(record.get("problems", [])) for record in recent_health
        )
        problem_rate = total_problems / len(recent_health) if recent_health else 0.0

        return {
            "total_checks": len(self.health_history),
            "recent_checks": len(recent_health),
            "avg_resource_usage": {
                "cpu_percent": avg_cpu,
                "memory_percent": avg_memory,
                "disk_percent": avg_disk,
            },
            "problem_rate": problem_rate,
            "total_problems": total_problems,
            "health_trend": self._calculate_health_trend(recent_health),
            "current_health": self._get_resource_usage(),
        }

    def _calculate_health_trend(self, recent_health: list[dict[str, Any]]) -> str:
        """Расчет тренда здоровья"""
        if len(recent_health) < 2:
            return "unknown"

        # Сравниваем количество проблем в начале и конце периода
        early_problems = len(recent_health[0].get("problems", []))
        late_problems = len(recent_health[-1].get("problems", []))

        if late_problems < early_problems:
            return "improving"
        if late_problems > early_problems:
            return "deteriorating"
        return "stable"

    def update_config(self, **kwargs):
        """Обновление конфигурации"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        self.config.updated_at = datetime.utcnow()
        self.logger.info(f"Updated health guard config: {kwargs}")

    def reset(self):
        """Сброс health guard"""
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.trigger_count = 0
        self.guard_state.last_triggered = None
        self.guard_state.last_recovery = None
        self.guard_state.updated_at = datetime.utcnow()

        # Очищаем историю
        self.health_history.clear()
        self.metrics_history.clear()

        self.logger.info("Health Guard reset")

    def set_callbacks(
        self,
        on_trigger: Callable | None = None,
        on_recovery: Callable | None = None,
    ):
        """Установка callbacks"""
        self.on_trigger_callback = on_trigger
        self.on_recovery_callback = on_recovery

        self.logger.info("Health Guard callbacks set")

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


class HealthGuardManager:
    """
    Менеджер health guards

    Управляет множественными health guards для разных компонентов системы
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.health_guards: dict[str, HealthGuard] = {}

    def create_health_guard(
        self, name: str, config: HealthGuardConfig | None = None
    ) -> HealthGuard:
        """Создание health guard"""
        if name in self.health_guards:
            raise ValueError(f"Health Guard '{name}' already exists")

        if config is None:
            config = HealthGuardConfig(guard_type=GuardType.HEALTH_GUARD, name=name)

        health_guard = HealthGuard(config)
        self.health_guards[name] = health_guard

        self.logger.info(f"Created Health Guard: {name}")
        return health_guard

    def get_health_guard(self, name: str) -> HealthGuard | None:
        """Получение health guard"""
        return self.health_guards.get(name)

    def check_system_health(self, name: str) -> tuple[bool, list[str]]:
        """Проверка здоровья системы через health guard"""
        health_guard = self.get_health_guard(name)
        if health_guard is None:
            raise ValueError(f"Health Guard '{name}' not found")

        return health_guard.check_system_health()

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Получение статуса всех health guards"""
        return {
            name: health_guard.get_status()
            for name, health_guard in self.health_guards.items()
        }

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Получение метрик всех health guards"""
        return {
            name: health_guard.get_metrics()
            for name, health_guard in self.health_guards.items()
        }

    def get_overall_health(self) -> dict[str, Any]:
        """Получение общего здоровья системы"""
        if not self.health_guards:
            return {"message": "No health guards available"}

        total_health = 0.0
        total_guards = len(self.health_guards)

        for health_guard in self.health_guards.values():
            metrics = health_guard.get_metrics()
            health_score = metrics.get("avg_health_score", 0.0)
            total_health += health_score

        avg_health = total_health / total_guards if total_guards > 0 else 0.0

        return {
            "overall_health_score": avg_health,
            "total_guards": total_guards,
            "health_by_guard": {
                name: health_guard.get_metrics().get("avg_health_score", 0.0)
                for name, health_guard in self.health_guards.items()
            },
        }

    def reset_all(self):
        """Сброс всех health guards"""
        for health_guard in self.health_guards.values():
            health_guard.reset()

        self.logger.info("All health guards reset")

    def check_all_recovery(self):
        """Проверка восстановления всех health guards"""
        for health_guard in self.health_guards.values():
            health_guard.check_recovery()
