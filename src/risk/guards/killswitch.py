"""
Kill Switch - экстренное отключение системы

Основные функции:
- Экстренное отключение системы при критических ситуациях
- Ручное управление состоянием системы
- Автоматическое отключение при превышении порогов
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
    GuardAlert,
    GuardMetrics,
    GuardState,
    GuardStatus,
    GuardType,
    KillSwitchConfig,
    KillSwitchStateData,
)

logger = logging.getLogger(__name__)


class KillSwitch:
    """
    Kill Switch для экстренного отключения системы

    Основные функции:
    - Экстренное отключение системы при критических ситуациях
    - Ручное управление состоянием системы
    - Автоматическое отключение при превышении порогов
    - Интеграция с системой уведомлений
    """

    def __init__(
        self,
        config: KillSwitchConfig | None = None,
        db_client: RiskDatabaseClient | None = None,
    ):
        self.config = config or KillSwitchConfig(
            guard_type=GuardType.KILL_SWITCH, name="default_killswitch"
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._db_client = db_client

        # Состояние kill switch
        self.state = KillSwitchStateData()

        # Состояние guard
        self.guard_state = GuardState(guard_id=uuid4(), status=GuardStatus.ACTIVE)

        # Метрики
        self.metrics_history: list[GuardMetrics] = []

        # Алерты
        self.alerts: list[GuardAlert] = []

        # Callbacks
        self.on_disable_callback: Callable | None = None
        self.on_enable_callback: Callable | None = None
        self.on_emergency_callback: Callable | None = None

    def is_enabled(self) -> bool:
        """Проверка включенности системы"""
        return self.state.is_enabled()

    def is_disabled(self) -> bool:
        """Проверка отключенности системы"""
        return self.state.is_disabled()

    def is_emergency(self) -> bool:
        """Проверка экстренного состояния"""
        return self.state.is_emergency()

    def can_operate(self) -> bool:
        """Проверка возможности выполнения операций"""
        return self.is_enabled() and not self.is_emergency()

    def disable(self, reason: str, disabled_by: str):
        """
        Отключение системы

        Args:
            reason: Причина отключения
            disabled_by: Кто отключил систему
        """
        if not self.config.manual_override:
            raise KillSwitchException("Manual override is disabled")

        self.state.disable(reason, disabled_by)
        self.guard_state.status = GuardStatus.TRIGGERED
        self.guard_state.trigger_count += 1
        self.guard_state.last_triggered = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="killswitch_disabled",
            severity="high",
            message=f"Kill switch disabled: {reason}",
            context={
                "reason": reason,
                "disabled_by": disabled_by,
                "disabled_at": self.state.disabled_at,
            },
        )
        self.alerts.append(alert)
        # persist
        self._log_guard_state("disabled")
        self._log_alert("killswitch_disabled", "high", alert.message, alert.context)

        # Вызываем callback
        if self.on_disable_callback:
            self.on_disable_callback(self, reason, disabled_by)

        self.logger.warning(f"Kill switch disabled: {reason} by {disabled_by}")

    def enable(self):
        """Включение системы"""
        if not self.config.manual_override:
            raise KillSwitchException("Manual override is disabled")

        self.state.enable()
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.last_recovery = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="killswitch_enabled",
            severity="medium",
            message="Kill switch enabled: system operational",
            context={
                "enabled_at": datetime.utcnow(),
                "previous_state": self.state.state.value,
            },
        )
        self.alerts.append(alert)
        # persist
        self._log_guard_state("enabled")
        self._log_alert("killswitch_enabled", "medium", alert.message, alert.context)

        # Вызываем callback
        if self.on_enable_callback:
            self.on_enable_callback(self)

        self.logger.info("Kill switch enabled: system operational")

    def trigger_emergency(self, reason: str):
        """
        Экстренное отключение системы

        Args:
            reason: Причина экстренного отключения
        """
        self.state.trigger_emergency(reason)
        self.guard_state.status = GuardStatus.TRIGGERED
        self.guard_state.trigger_count += 1
        self.guard_state.last_triggered = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="killswitch_emergency",
            severity="critical",
            message=f"Kill switch emergency: {reason}",
            context={
                "reason": reason,
                "emergency_at": self.state.emergency_at,
                "auto_disable": self.config.auto_disable_on_emergency,
            },
        )
        self.alerts.append(alert)
        # persist
        self._log_guard_state("emergency")
        self._log_alert(
            "killswitch_emergency", "critical", alert.message, alert.context
        )

        # Вызываем callback
        if self.on_emergency_callback:
            self.on_emergency_callback(self, reason)

        self.logger.critical(f"Kill switch emergency: {reason}")

    # --- Persistence helpers ---
    def _fire_and_forget(self, coro: Awaitable[Any] | None) -> None:
        if coro is None:
            return
        try:
            import asyncio

            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            pass

    def _log_metric(
        self, metric_name: str, metric_value: Decimal, labels: dict[str, Any]
    ) -> None:
        if not self._db_client:
            return

        async def write():
            await self._db_client.upsert_guard(
                self.config.name,
                self.config.guard_type.value,
                (
                    "active"
                    if self.guard_state.status == GuardStatus.ACTIVE
                    else "triggered"
                ),
                {"source": "ks"},
            )
            await self._db_client.add_metric(
                self.guard_state.guard_id, metric_name, metric_value, labels
            )

        self._fire_and_forget(write())

    def _log_alert(
        self, alert_type: str, severity: str, message: str, context: dict[str, Any]
    ) -> None:
        if not self._db_client:
            return

        async def write():
            await self._db_client.upsert_guard(
                self.config.name,
                self.config.guard_type.value,
                (
                    "active"
                    if self.guard_state.status == GuardStatus.ACTIVE
                    else "triggered"
                ),
                {"source": "ks"},
            )
            await self._db_client.add_alert(
                self.guard_state.guard_id, alert_type, severity, message, context
            )

        self._fire_and_forget(write())

    def _log_guard_state(self, state: str) -> None:
        if not self._db_client:
            return

        async def write():
            await self._db_client.upsert_guard(
                self.config.name,
                self.config.guard_type.value,
                (
                    "active"
                    if self.guard_state.status == GuardStatus.ACTIVE
                    else "triggered"
                ),
                {"source": "ks"},
            )
            await self._db_client.add_guard_state(
                self.guard_state.guard_id,
                state,
                self.guard_state.trigger_count,
                {"ks_state": self.state.state.value, "name": self.config.name},
            )

        self._fire_and_forget(write())

    def check_emergency_threshold(self, metric_value: Decimal):
        """
        Проверка порога экстренного отключения

        Args:
            metric_value: Значение метрики
        """
        if metric_value >= self.config.emergency_threshold:
            reason = f"Emergency threshold exceeded: {metric_value} >= {self.config.emergency_threshold}"
            self.trigger_emergency(reason)

            if self.config.auto_disable_on_emergency:
                self.disable(reason, "system")

    def get_status(self) -> dict[str, Any]:
        """Получение статуса kill switch"""
        return {
            "state": self.state.state.value,
            "is_enabled": self.is_enabled(),
            "is_disabled": self.is_disabled(),
            "is_emergency": self.is_emergency(),
            "can_operate": self.can_operate(),
            "disabled_reason": self.state.disabled_reason,
            "disabled_by": self.state.disabled_by,
            "disabled_at": self.state.disabled_at,
            "emergency_triggered": self.state.emergency_triggered,
            "emergency_reason": self.state.emergency_reason,
            "emergency_at": self.state.emergency_at,
            "guard_status": self.guard_state.status.value,
            "trigger_count": self.guard_state.trigger_count,
            "last_triggered": self.guard_state.last_triggered,
            "last_recovery": self.guard_state.last_recovery,
            "config": {
                "emergency_threshold": float(self.config.emergency_threshold),
                "auto_disable_on_emergency": self.config.auto_disable_on_emergency,
                "manual_override": self.config.manual_override,
            },
        }

    def get_metrics(self) -> dict[str, Any]:
        """Получение метрик kill switch"""
        if not self.metrics_history:
            return {}

        recent_metrics = self.metrics_history[-10:]  # Последние 10 записей

        return {
            "current_state": self.state.state.value,
            "is_operational": self.can_operate(),
            "total_disables": self.guard_state.trigger_count,
            "last_disable": self.state.disabled_at,
            "last_emergency": self.state.emergency_at,
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
        self.logger.info(f"Updated kill switch config: {kwargs}")

    def reset(self):
        """Сброс kill switch"""
        self.state = KillSwitchStateData()
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.trigger_count = 0
        self.guard_state.last_triggered = None
        self.guard_state.last_recovery = None
        self.guard_state.updated_at = datetime.utcnow()

        self.logger.info("Kill switch reset")

    def set_callbacks(
        self,
        on_disable: Callable | None = None,
        on_enable: Callable | None = None,
        on_emergency: Callable | None = None,
    ):
        """Установка callbacks"""
        self.on_disable_callback = on_disable
        self.on_enable_callback = on_enable
        self.on_emergency_callback = on_emergency

        self.logger.info("Kill switch callbacks set")

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


class KillSwitchException(Exception):
    """Исключение kill switch"""

    pass


class KillSwitchManager:
    """
    Менеджер kill switches

    Управляет множественными kill switches для разных компонентов системы
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.kill_switches: dict[str, KillSwitch] = {}

    def create_kill_switch(
        self, name: str, config: KillSwitchConfig | None = None
    ) -> KillSwitch:
        """Создание kill switch"""
        if name in self.kill_switches:
            raise ValueError(f"Kill switch '{name}' already exists")

        if config is None:
            config = KillSwitchConfig(guard_type=GuardType.KILL_SWITCH, name=name)

        kill_switch = KillSwitch(config)
        self.kill_switches[name] = kill_switch

        self.logger.info(f"Created kill switch: {name}")
        return kill_switch

    def get_kill_switch(self, name: str) -> KillSwitch | None:
        """Получение kill switch"""
        return self.kill_switches.get(name)

    def is_system_operational(self) -> bool:
        """Проверка операционности системы"""
        return all(ks.can_operate() for ks in self.kill_switches.values())

    def disable_system(self, reason: str, disabled_by: str):
        """Отключение всей системы"""
        for name, ks in self.kill_switches.items():
            try:
                ks.disable(f"{reason} (system-wide)", disabled_by)
            except KillSwitchException as e:
                self.logger.warning(f"Failed to disable kill switch '{name}': {e}")

        self.logger.warning(f"System disabled: {reason} by {disabled_by}")

    def enable_system(self):
        """Включение всей системы"""
        for name, ks in self.kill_switches.items():
            try:
                ks.enable()
            except KillSwitchException as e:
                self.logger.warning(f"Failed to enable kill switch '{name}': {e}")

        self.logger.info("System enabled")

    def trigger_system_emergency(self, reason: str):
        """Экстренное отключение всей системы"""
        for _name, ks in self.kill_switches.items():
            ks.trigger_emergency(f"{reason} (system-wide)")

        self.logger.critical(f"System emergency: {reason}")

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Получение статуса всех kill switches"""
        return {name: ks.get_status() for name, ks in self.kill_switches.items()}

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Получение метрик всех kill switches"""
        return {name: ks.get_metrics() for name, ks in self.kill_switches.items()}

    def get_system_health(self) -> dict[str, Any]:
        """Получение здоровья системы"""
        operational_count = sum(
            1 for ks in self.kill_switches.values() if ks.can_operate()
        )
        total_count = len(self.kill_switches)

        return {
            "is_operational": self.is_system_operational(),
            "operational_count": operational_count,
            "total_count": total_count,
            "operational_percentage": (
                operational_count / total_count if total_count > 0 else 0.0
            ),
            "kill_switches": {
                name: {
                    "is_operational": ks.can_operate(),
                    "state": ks.state.state.value,
                    "is_emergency": ks.is_emergency(),
                }
                for name, ks in self.kill_switches.items()
            },
        }

    def reset_all(self):
        """Сброс всех kill switches"""
        for ks in self.kill_switches.values():
            ks.reset()

        self.logger.info("All kill switches reset")
