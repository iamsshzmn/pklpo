"""
Модели для модуля предохранителей риска

Расширяет базовые модели из risk/models.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


class GuardType(Enum):
    """Тип предохранителя"""

    CIRCUIT_BREAKER = "circuit_breaker"
    KILL_SWITCH = "killswitch"
    DQ_GUARD = "dq_guard"
    SLA_GUARD = "sla_guard"
    HEALTH_GUARD = "health_guard"


class GuardStatus(Enum):
    """Статус предохранителя"""

    ACTIVE = "active"
    TRIGGERED = "triggered"
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"


class CircuitBreakerState(Enum):
    """Состояние circuit breaker"""

    CLOSED = "closed"  # Нормальная работа
    OPENED = "opened"  # Отключен, блокирует операции
    HALF_OPEN = "half_open"  # Тестирует восстановление


class KillSwitchState(Enum):
    """Состояние kill switch"""

    ENABLED = "enabled"  # Система работает
    DISABLED = "disabled"  # Система отключена
    EMERGENCY = "emergency"  # Экстренное отключение


@dataclass
class GuardConfiguration:
    """Конфигурация предохранителя"""

    guard_type: GuardType
    name: str
    enabled: bool = True
    threshold: Decimal = Decimal("0.8")  # Порог срабатывания
    cooldown_sec: int = 300  # Кулдаун после срабатывания
    max_trigger_count: int = 3  # Максимум срабатываний
    auto_recovery: bool = True  # Автоматическое восстановление
    notification_enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CircuitBreakerConfig(GuardConfiguration):
    """Конфигурация circuit breaker"""

    failure_threshold: int = 5  # Количество ошибок для срабатывания
    recovery_threshold: int = 2  # Количество успешных операций для восстановления
    timeout_sec: int = 60  # Таймаут для операций
    half_open_max_calls: int = 3  # Максимум вызовов в half-open состоянии


@dataclass
class KillSwitchConfig(GuardConfiguration):
    """Конфигурация kill switch"""

    emergency_threshold: Decimal = Decimal("0.95")  # Порог экстренного отключения
    auto_disable_on_emergency: bool = (
        True  # Автоматическое отключение при экстренной ситуации
    )
    manual_override: bool = True  # Возможность ручного управления


@dataclass
class DQGuardConfig(GuardConfiguration):
    """Конфигурация DQ guard"""

    data_freshness_threshold_sec: int = 300  # Максимальный возраст данных
    data_quality_threshold: Decimal = Decimal("0.9")  # Минимальное качество данных
    missing_data_threshold: Decimal = Decimal(
        "0.1"
    )  # Максимальный процент отсутствующих данных
    anomaly_threshold: Decimal = Decimal("3.0")  # Порог аномалий (в сигмах)


@dataclass
class SLAGuardConfig(GuardConfiguration):
    """Конфигурация SLA guard"""

    latency_threshold_ms: int = 1000  # Максимальная задержка
    throughput_threshold: int = 100  # Минимальная пропускная способность
    error_rate_threshold: Decimal = Decimal("0.05")  # Максимальный процент ошибок
    availability_threshold: Decimal = Decimal("0.99")  # Минимальная доступность


@dataclass
class HealthGuardConfig(GuardConfiguration):
    """Конфигурация health guard"""

    memory_threshold: Decimal = Decimal("0.8")  # Максимальное использование памяти
    cpu_threshold: Decimal = Decimal("0.8")  # Максимальное использование CPU
    disk_threshold: Decimal = Decimal("0.9")  # Максимальное использование диска
    connection_threshold: int = 100  # Максимальное количество соединений


@dataclass
class GuardState:
    """Состояние предохранителя"""

    guard_id: UUID
    status: GuardStatus = GuardStatus.ACTIVE
    trigger_count: int = 0
    last_triggered: datetime | None = None
    last_recovery: datetime | None = None
    current_metric: Decimal = Decimal("0.0")
    threshold_exceeded: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_triggered(self) -> bool:
        """Проверка срабатывания"""
        return self.status == GuardStatus.TRIGGERED

    def can_recover(self, config: GuardConfiguration) -> bool:
        """Проверка возможности восстановления"""
        if not config.auto_recovery:
            return False

        if self.last_triggered is None:
            return True

        time_since_trigger = datetime.utcnow() - self.last_triggered
        return time_since_trigger.total_seconds() >= config.cooldown_sec

    def should_trigger(self, config: GuardConfiguration) -> bool:
        """Проверка необходимости срабатывания"""
        return (
            self.current_metric >= config.threshold
            and not self.is_triggered()
            and self.trigger_count < config.max_trigger_count
        )


@dataclass
class CircuitBreakerStateData:
    """Состояние circuit breaker"""

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure: datetime | None = None
    last_success: datetime | None = None
    half_open_calls: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def record_failure(self):
        """Запись ошибки"""
        self.failure_count += 1
        self.last_failure = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def record_success(self):
        """Запись успеха"""
        self.success_count += 1
        self.last_success = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def should_open(self, config: CircuitBreakerConfig) -> bool:
        """Проверка необходимости открытия"""
        return (
            self.state == CircuitBreakerState.CLOSED
            and self.failure_count >= config.failure_threshold
        )

    def should_close(self, config: CircuitBreakerConfig) -> bool:
        """Проверка необходимости закрытия"""
        return (
            self.state == CircuitBreakerState.HALF_OPEN
            and self.success_count >= config.recovery_threshold
        )

    def should_half_open(self, config: CircuitBreakerConfig) -> bool:
        """Проверка необходимости перехода в half-open"""
        if self.state != CircuitBreakerState.OPEN:
            return False

        if self.last_failure is None:
            return True

        time_since_failure = datetime.utcnow() - self.last_failure
        return time_since_failure.total_seconds() >= config.cooldown_sec


@dataclass
class KillSwitchStateData:
    """Состояние kill switch"""

    state: KillSwitchState = KillSwitchState.ENABLED
    disabled_reason: str | None = None
    disabled_by: str | None = None
    disabled_at: datetime | None = None
    emergency_triggered: bool = False
    emergency_reason: str | None = None
    emergency_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_enabled(self) -> bool:
        """Проверка включенности системы"""
        return self.state == KillSwitchState.ENABLED

    def is_disabled(self) -> bool:
        """Проверка отключенности системы"""
        return self.state in [KillSwitchState.DISABLED, KillSwitchState.EMERGENCY]

    def is_emergency(self) -> bool:
        """Проверка экстренного состояния"""
        return self.state == KillSwitchState.EMERGENCY

    def disable(self, reason: str, disabled_by: str):
        """Отключение системы"""
        self.state = KillSwitchState.DISABLED
        self.disabled_reason = reason
        self.disabled_by = disabled_by
        self.disabled_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def enable(self):
        """Включение системы"""
        self.state = KillSwitchState.ENABLED
        self.disabled_reason = None
        self.disabled_by = None
        self.disabled_at = None
        self.updated_at = datetime.utcnow()

    def trigger_emergency(self, reason: str):
        """Экстренное отключение"""
        self.state = KillSwitchState.EMERGENCY
        self.emergency_triggered = True
        self.emergency_reason = reason
        self.emergency_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


@dataclass
class GuardMetrics:
    """Метрики предохранителя"""

    guard_id: UUID
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metric_value: Decimal = Decimal("0.0")
    threshold_value: Decimal = Decimal("0.0")
    is_triggered: bool = False
    trigger_count: int = 0
    recovery_count: int = 0
    last_trigger_duration_sec: int | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardAlert:
    """Алерт предохранителя"""

    guard_id: UUID
    alert_type: str
    severity: str  # low, medium, high, critical
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None

    def acknowledge(self, acknowledged_by: str):
        """Подтверждение алерта"""
        self.acknowledged = True
        self.acknowledged_by = acknowledged_by
        self.acknowledged_at = datetime.utcnow()


@dataclass
class GuardSnapshot:
    """Снимок состояния всех предохранителей"""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    guards: dict[str, GuardState] = field(default_factory=dict)
    circuit_breakers: dict[str, CircuitBreakerState] = field(default_factory=dict)
    kill_switches: dict[str, KillSwitchState] = field(default_factory=dict)
    active_alerts: list[GuardAlert] = field(default_factory=list)
    system_health: dict[str, Any] = field(default_factory=dict)

    def get_summary(self) -> dict[str, Any]:
        """Получение сводки по предохранителям"""
        total_guards = len(self.guards)
        triggered_guards = sum(1 for g in self.guards.values() if g.is_triggered())
        active_circuit_breakers = sum(
            1
            for cb in self.circuit_breakers.values()
            if cb.state == CircuitBreakerState.OPEN
        )
        disabled_kill_switches = sum(
            1 for ks in self.kill_switches.values() if ks.is_disabled()
        )

        return {
            "timestamp": self.timestamp,
            "total_guards": total_guards,
            "triggered_guards": triggered_guards,
            "active_circuit_breakers": active_circuit_breakers,
            "disabled_kill_switches": disabled_kill_switches,
            "active_alerts": len(self.active_alerts),
            "system_health": self.system_health,
        }
