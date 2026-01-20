"""
Модели для модуля управления лимитами риска

Расширяет базовые модели из risk/models.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from ..models import RiskLimitType, RiskViolation


class LimitStatus(Enum):
    """Статус лимита"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXCEEDED = "exceeded"
    RESET_PENDING = "reset_pending"


class LimitResetPeriod(Enum):
    """Период сброса лимита"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    NEVER = "never"


@dataclass
class LimitConfiguration:
    """Конфигурация лимита"""

    limit_type: RiskLimitType
    limit_value: Decimal
    reset_period: LimitResetPeriod
    warning_threshold: Decimal = Decimal("0.8")  # 80% от лимита
    critical_threshold: Decimal = Decimal("0.95")  # 95% от лимита
    auto_reset: bool = True
    notifications_enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LimitState:
    """Состояние лимита"""

    limit_id: UUID
    current_value: Decimal = Decimal("0.0")
    last_reset: datetime = field(default_factory=datetime.utcnow)
    next_reset: datetime | None = None
    status: LimitStatus = LimitStatus.ACTIVE
    violation_count: int = 0
    last_violation: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def is_warning_threshold_reached(self, config: LimitConfiguration) -> bool:
        """Проверка достижения порога предупреждения"""
        return self.current_value >= config.limit_value * config.warning_threshold

    def is_critical_threshold_reached(self, config: LimitConfiguration) -> bool:
        """Проверка достижения критического порога"""
        return self.current_value >= config.limit_value * config.critical_threshold

    def is_exceeded(self, config: LimitConfiguration) -> bool:
        """Проверка превышения лимита"""
        return self.current_value >= config.limit_value

    def get_remaining(self, config: LimitConfiguration) -> Decimal:
        """Получение оставшегося лимита"""
        return max(Decimal("0.0"), config.limit_value - self.current_value)

    def get_usage_percentage(self, config: LimitConfiguration) -> float:
        """Получение процента использования лимита"""
        if config.limit_value == 0:
            return 0.0
        return float(self.current_value / config.limit_value)

    def should_reset(self, config: LimitConfiguration) -> bool:
        """Проверка необходимости сброса лимита"""
        if not config.auto_reset or self.next_reset is None:
            return False
        return datetime.utcnow() >= self.next_reset


@dataclass
class DailyLimitsState:
    """Состояние дневных лимитов"""

    date: datetime
    daily_loss: Decimal = Decimal("0.0")
    daily_trades: int = 0
    daily_volume: Decimal = Decimal("0.0")
    daily_fees: Decimal = Decimal("0.0")
    last_trade_time: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_trade(self, pnl: Decimal, volume: Decimal, fees: Decimal):
        """Добавление сделки к дневным лимитам"""
        self.daily_loss += pnl
        self.daily_trades += 1
        self.daily_volume += volume
        self.daily_fees += fees
        self.last_trade_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def is_new_day(self) -> bool:
        """Проверка, начался ли новый день"""
        return self.date.date() != datetime.utcnow().date()

    def reset_for_new_day(self):
        """Сброс для нового дня"""
        self.date = datetime.utcnow()
        self.daily_loss = Decimal("0.0")
        self.daily_trades = 0
        self.daily_volume = Decimal("0.0")
        self.daily_fees = Decimal("0.0")
        self.last_trade_time = None
        self.updated_at = datetime.utcnow()


@dataclass
class WeeklyLimitsState:
    """Состояние недельных лимитов"""

    week_start: datetime
    weekly_loss: Decimal = Decimal("0.0")
    weekly_trades: int = 0
    weekly_volume: Decimal = Decimal("0.0")
    weekly_fees: Decimal = Decimal("0.0")
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_trade(self, pnl: Decimal, volume: Decimal, fees: Decimal):
        """Добавление сделки к недельным лимитам"""
        self.weekly_loss += pnl
        self.weekly_trades += 1
        self.weekly_volume += volume
        self.weekly_fees += fees
        self.updated_at = datetime.utcnow()

    def is_new_week(self) -> bool:
        """Проверка, началась ли новая неделя"""
        current_week = datetime.utcnow().isocalendar()[1]
        state_week = self.week_start.isocalendar()[1]
        return current_week != state_week

    def reset_for_new_week(self):
        """Сброс для новой недели"""
        self.week_start = datetime.utcnow()
        self.weekly_loss = Decimal("0.0")
        self.weekly_trades = 0
        self.weekly_volume = Decimal("0.0")
        self.weekly_fees = Decimal("0.0")
        self.updated_at = datetime.utcnow()


@dataclass
class PositionLimitsState:
    """Состояние лимитов позиций"""

    current_positions: int = 0
    max_positions: int = 10
    total_position_value: Decimal = Decimal("0.0")
    max_position_value: Decimal = Decimal("10000.0")
    position_symbols: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_position(self, symbol: str, value: Decimal) -> bool:
        """Добавление позиции"""
        if self.current_positions >= self.max_positions:
            return False

        if self.total_position_value + value > self.max_position_value:
            return False

        self.current_positions += 1
        self.total_position_value += value
        self.position_symbols.add(symbol)
        self.updated_at = datetime.utcnow()
        return True

    def remove_position(self, symbol: str, value: Decimal):
        """Удаление позиции"""
        if symbol in self.position_symbols:
            self.current_positions = max(0, self.current_positions - 1)
            self.total_position_value = max(
                Decimal("0.0"), self.total_position_value - value
            )
            self.position_symbols.discard(symbol)
            self.updated_at = datetime.utcnow()

    def can_add_position(self, value: Decimal) -> bool:
        """Проверка возможности добавления позиции"""
        return (
            self.current_positions < self.max_positions
            and self.total_position_value + value <= self.max_position_value
        )


@dataclass
class CorrelationLimitsState:
    """Состояние лимитов корреляции"""

    symbol_correlations: dict[str, dict[str, float]] = field(default_factory=dict)
    max_correlation: float = 0.7
    correlation_window_days: int = 30
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_correlation(self, symbol1: str, symbol2: str, correlation: float):
        """Добавление корреляции между символами"""
        if symbol1 not in self.symbol_correlations:
            self.symbol_correlations[symbol1] = {}
        if symbol2 not in self.symbol_correlations:
            self.symbol_correlations[symbol2] = {}

        self.symbol_correlations[symbol1][symbol2] = correlation
        self.symbol_correlations[symbol2][symbol1] = correlation
        self.updated_at = datetime.utcnow()

    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Получение корреляции между символами"""
        if symbol1 in self.symbol_correlations:
            return self.symbol_correlations[symbol1].get(symbol2, 0.0)
        return 0.0

    def check_correlation_limit(
        self, new_symbol: str, existing_symbols: list[str]
    ) -> bool:
        """Проверка лимита корреляции для нового символа"""
        for existing_symbol in existing_symbols:
            correlation = self.get_correlation(new_symbol, existing_symbol)
            if abs(correlation) > self.max_correlation:
                return False
        return True


@dataclass
class CooldownLimitsState:
    """Состояние кулдаунов"""

    last_trade_time: datetime | None = None
    last_loss_time: datetime | None = None
    cooldown_between_trades_sec: int = 300  # 5 минут
    cooldown_after_loss_sec: int = 3600  # 1 час
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def can_trade(self) -> bool:
        """Проверка возможности торговли"""
        now = datetime.utcnow()

        # Проверка кулдауна между сделками
        if self.last_trade_time:
            time_since_last_trade = now - self.last_trade_time
            if time_since_last_trade.total_seconds() < self.cooldown_between_trades_sec:
                return False

        # Проверка кулдауна после убытка
        if self.last_loss_time:
            time_since_last_loss = now - self.last_loss_time
            if time_since_last_loss.total_seconds() < self.cooldown_after_loss_sec:
                return False

        return True

    def record_trade(self, pnl: Decimal):
        """Запись сделки"""
        self.last_trade_time = datetime.utcnow()
        if pnl < 0:  # Убыточная сделка
            self.last_loss_time = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def get_remaining_cooldown(self) -> int:
        """Получение оставшегося времени кулдауна в секундах"""
        now = datetime.utcnow()
        remaining = 0

        # Кулдаун между сделками
        if self.last_trade_time:
            time_since_last_trade = now - self.last_trade_time
            trade_cooldown = max(
                0,
                self.cooldown_between_trades_sec
                - time_since_last_trade.total_seconds(),
            )
            remaining = max(remaining, trade_cooldown)

        # Кулдаун после убытка
        if self.last_loss_time:
            time_since_last_loss = now - self.last_loss_time
            loss_cooldown = max(
                0, self.cooldown_after_loss_sec - time_since_last_loss.total_seconds()
            )
            remaining = max(remaining, loss_cooldown)

        return int(remaining)


@dataclass
class LimitsSnapshot:
    """Снимок состояния всех лимитов"""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    daily_limits: DailyLimitsState = field(default_factory=DailyLimitsState)
    weekly_limits: WeeklyLimitsState = field(default_factory=WeeklyLimitsState)
    position_limits: PositionLimitsState = field(default_factory=PositionLimitsState)
    correlation_limits: CorrelationLimitsState = field(
        default_factory=CorrelationLimitsState
    )
    cooldown_limits: CooldownLimitsState = field(default_factory=CooldownLimitsState)
    violations: list[RiskViolation] = field(default_factory=list)

    def get_summary(self) -> dict[str, Any]:
        """Получение сводки по лимитам"""
        return {
            "timestamp": self.timestamp,
            "daily_loss": float(self.daily_limits.daily_loss),
            "daily_trades": self.daily_limits.daily_trades,
            "weekly_loss": float(self.weekly_limits.weekly_loss),
            "weekly_trades": self.weekly_limits.weekly_trades,
            "current_positions": self.position_limits.current_positions,
            "max_positions": self.position_limits.max_positions,
            "total_position_value": float(self.position_limits.total_position_value),
            "can_trade": self.cooldown_limits.can_trade(),
            "remaining_cooldown": self.cooldown_limits.get_remaining_cooldown(),
            "violations_count": len(self.violations),
        }
