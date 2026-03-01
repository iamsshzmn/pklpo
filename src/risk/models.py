"""
Модели данных для модуля управления рисками (Фаза 5)

Основные модели:
- RiskConfig: конфигурация модуля
- RiskLimit: лимиты риска
- CircuitBreakerState: состояние circuit breaker
- KillSwitchState: состояние killswitch
- PositionSizeRequest/Result: запрос и результат расчета размера позиции
- RiskViolation: нарушение лимитов
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class RiskLimitType(Enum):
    """Типы лимитов риска"""

    DAILY_LOSS = "daily_loss"
    WEEKLY_LOSS = "weekly_loss"
    MAX_CONCURRENT = "max_concurrent"
    MAX_CORRELATION = "max_correlation"
    COOLDOWN = "cooldown"
    MAX_POSITION_SIZE = "max_position_size"
    MAX_LEVERAGE = "max_leverage"


class CircuitBreakerState(Enum):
    """Состояния circuit breaker"""

    CLOSED = "closed"  # Нормальная работа
    OPEN = "open"  # Блокировка
    HALF_OPEN = "half_open"  # Тестирование восстановления


class KillSwitchState(Enum):
    """Состояния killswitch"""

    INACTIVE = "inactive"  # Система работает
    ACTIVE = "active"  # Система заблокирована


@dataclass
class RiskConfig:
    """Конфигурация модуля управления рисками"""

    # Основные лимиты
    default_risk_per_trade: float = 0.02  # 2% от баланса
    max_risk_per_trade: float = 0.05  # 5% максимум
    daily_loss_limit: float = 0.10  # 10% дневной лимит потерь
    weekly_loss_limit: float = 0.20  # 20% недельный лимит потерь

    # Лимиты позиций
    max_concurrent_positions: int = 10
    max_position_size_usdt: float = 10000.0
    max_leverage: float = 20.0

    # Кулдауны
    cooldown_after_loss_sec: int = 3600  # 1 час после убытка
    cooldown_between_trades_sec: int = 300  # 5 минут между сделками

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5  # 5 неудач подряд
    circuit_breaker_timeout_sec: int = 1800  # 30 минут блокировки
    circuit_breaker_half_open_max_calls: int = 3  # 3 тестовых вызова

    # Killswitch
    enable_killswitch: bool = True
    killswitch_auto_activate_on_loss: float = 0.15  # 15% потерь

    # Data Quality
    min_data_quality_score: float = 0.8
    max_data_age_sec: int = 300  # 5 минут

    # SLA
    max_latency_ms: int = 1000  # 1 секунда
    min_throughput_per_min: int = 10  # 10 операций в минуту

    # Алерты
    enable_alerts: bool = True
    alert_channels: list[str] = field(default_factory=lambda: ["slack", "telegram"])

    def validate(self):
        """Валидация конфигурации"""
        if not 0 < self.default_risk_per_trade <= 1:
            raise ValueError(
                f"default_risk_per_trade must be between 0 and 1, got {self.default_risk_per_trade}"
            )

        if not 0 < self.daily_loss_limit <= 1:
            raise ValueError(
                f"daily_loss_limit must be between 0 and 1, got {self.daily_loss_limit}"
            )

        if self.max_concurrent_positions <= 0:
            raise ValueError(
                f"max_concurrent_positions must be positive, got {self.max_concurrent_positions}"
            )


@dataclass
class RiskLimit:
    """Лимит риска"""

    id: UUID = field(default_factory=uuid4)
    limit_type: RiskLimitType = RiskLimitType.DAILY_LOSS
    limit_value: Decimal = Decimal("0.0")
    current_value: Decimal = Decimal("0.0")
    reset_period: str = "daily"  # daily, weekly, monthly
    last_reset: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_exceeded(self) -> bool:
        """Проверка превышения лимита"""
        return self.current_value >= self.limit_value

    def get_remaining(self) -> Decimal:
        """Получение оставшегося лимита"""
        return max(Decimal("0.0"), self.limit_value - self.current_value)

    def add_value(self, value: Decimal) -> bool:
        """Добавление значения к текущему лимиту"""
        self.current_value += value
        self.updated_at = datetime.utcnow()
        return self.is_exceeded()

    def reset(self):
        """Сброс лимита"""
        self.current_value = Decimal("0.0")
        self.last_reset = datetime.utcnow()
        self.updated_at = datetime.utcnow()


@dataclass
class CircuitBreakerState:
    """Состояние circuit breaker"""

    id: UUID = field(default_factory=uuid4)
    breaker_name: str = "default"
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: datetime | None = None
    next_attempt_time: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def record_success(self):
        """Запись успешной операции"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.next_attempt_time = None
        self.updated_at = datetime.utcnow()

    def record_failure(self):
        """Запись неудачной операции"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def should_attempt_reset(self) -> bool:
        """Проверка возможности попытки сброса"""
        if self.state != CircuitBreakerState.OPEN:
            return False

        if self.next_attempt_time is None:
            return False

        return datetime.utcnow() >= self.next_attempt_time


@dataclass
class KillSwitchState:
    """Состояние killswitch"""

    id: UUID = field(default_factory=uuid4)
    switch_name: str = "default"
    is_active: bool = False
    reason: str | None = None
    activated_by: str | None = None
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def activate(self, reason: str, activated_by: str = "system"):
        """Активация killswitch"""
        self.is_active = True
        self.reason = reason
        self.activated_by = activated_by
        self.activated_at = datetime.utcnow()

    def deactivate(self):
        """Деактивация killswitch"""
        self.is_active = False
        self.deactivated_at = datetime.utcnow()


@dataclass
class PositionSizeRequest:
    """Запрос на расчет размера позиции"""

    symbol: str
    balance: Decimal
    entry_price: Decimal
    stop_price: Decimal
    risk_per_trade: Decimal
    fees_bps: int = 10  # 0.1%
    slippage_bps: int = 5  # 0.05%
    lot_size: Decimal = Decimal("1.0")
    max_leverage: Decimal = Decimal("20.0")
    current_positions: int = 0
    max_concurrent: int = 10

    def validate(self):
        """Валидация запроса"""
        if self.balance <= 0:
            raise ValueError(f"Balance must be positive, got {self.balance}")

        if self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {self.entry_price}")

        if self.stop_price <= 0:
            raise ValueError(f"Stop price must be positive, got {self.stop_price}")

        if not 0 < self.risk_per_trade <= 1:
            raise ValueError(
                f"Risk per trade must be between 0 and 1, got {self.risk_per_trade}"
            )


@dataclass
class PositionSizeResult:
    """Результат расчета размера позиции"""

    is_valid: bool
    position_size: Decimal = Decimal("0.0")
    position_value: Decimal = Decimal("0.0")
    risk_amount: Decimal = Decimal("0.0")
    leverage_used: Decimal = Decimal("0.0")
    margin_required: Decimal = Decimal("0.0")
    liquidation_distance: Decimal = Decimal("0.0")
    risk_reward_ratio: Decimal = Decimal("0.0")
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, error: str):
        """Добавление ошибки"""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Добавление предупреждения"""
        self.warnings.append(warning)


@dataclass
class RiskViolation:
    """Нарушение лимитов риска"""

    limit_id: UUID
    violation_type: str
    violation_value: Decimal
    limit_value: Decimal
    id: UUID = field(default_factory=uuid4)
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def get_severity(self) -> str:
        """Получение уровня серьезности нарушения"""
        ratio = float(self.violation_value / self.limit_value)

        if ratio >= 2.0:
            return "critical"
        if ratio >= 1.5:
            return "high"
        if ratio >= 1.0:
            return "medium"
        return "low"


@dataclass
class DataQualityMetrics:
    """Метрики качества данных"""

    symbol: str
    data_freshness_sec: int
    data_completeness: float  # 0-1
    data_accuracy: float  # 0-1
    overall_score: float  # 0-1
    last_update: datetime = field(default_factory=datetime.utcnow)

    def is_acceptable(self, min_score: float = 0.8) -> bool:
        """Проверка приемлемости качества данных"""
        return self.overall_score >= min_score


@dataclass
class SLAMetrics:
    """Метрики SLA"""

    operation_type: str
    latency_ms: int
    throughput_per_min: int
    success_rate: float  # 0-1
    last_check: datetime = field(default_factory=datetime.utcnow)

    def is_acceptable(
        self, max_latency_ms: int = 1000, min_throughput: int = 10
    ) -> bool:
        """Проверка соответствия SLA"""
        return (
            self.latency_ms <= max_latency_ms
            and self.throughput_per_min >= min_throughput
            and self.success_rate >= 0.95
        )


# Типы для API
RiskLimitRequest = dict[str, Any]
PositionSizeRequestDict = dict[str, Any]
RiskViolationRequest = dict[str, Any]
