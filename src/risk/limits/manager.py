"""
Менеджер лимитов риска

Централизованное управление всеми лимитами:
- Дневные лимиты потерь
- Недельные лимиты потерь
- Лимиты позиций
- Лимиты корреляции
- Кулдауны
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from ..config import get_risk_config
from ..database.client import RiskDatabaseClient
from ..models import RiskConfig, RiskLimitType, RiskViolation
from .models import (
    CooldownLimitsState,
    CorrelationLimitsState,
    DailyLimitsState,
    LimitConfiguration,
    LimitResetPeriod,
    LimitsSnapshot,
    LimitState,
    LimitStatus,
    PositionLimitsState,
    WeeklyLimitsState,
)

logger = logging.getLogger(__name__)


class RiskLimitsManager:
    """
    Менеджер лимитов риска

    Основные функции:
    - Управление всеми типами лимитов
    - Проверка превышений
    - Автоматический сброс лимитов
    - Отслеживание нарушений
    - Интеграция с уведомлениями
    """

    def __init__(
        self,
        config: RiskConfig | None = None,
        db_client: RiskDatabaseClient | None = None,
    ):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._db_client = db_client

        # Состояния лимитов
        self.daily_limits = DailyLimitsState(date=datetime.utcnow())
        self.weekly_limits = WeeklyLimitsState(week_start=datetime.utcnow())
        self.position_limits = PositionLimitsState(
            max_positions=self.config.max_concurrent_positions,
            max_position_value=Decimal(str(self.config.max_position_size_usdt)),
        )
        self.correlation_limits = CorrelationLimitsState()
        self.cooldown_limits = CooldownLimitsState(
            cooldown_between_trades_sec=self.config.cooldown_between_trades_sec,
            cooldown_after_loss_sec=self.config.cooldown_after_loss_sec,
        )

        # Конфигурации лимитов
        self.limit_configs: dict[RiskLimitType, LimitConfiguration] = {}
        self.limit_states: dict[RiskLimitType, LimitState] = {}

        # История нарушений
        self.violations: list[RiskViolation] = []

        # Инициализация лимитов
        self._initialize_limits()

    def _initialize_limits(self):
        """Инициализация лимитов на основе конфигурации"""

        # Дневной лимит потерь
        self.limit_configs[RiskLimitType.DAILY_LOSS] = LimitConfiguration(
            limit_type=RiskLimitType.DAILY_LOSS,
            limit_value=Decimal(str(self.config.daily_loss_limit)),
            reset_period=LimitResetPeriod.DAILY,
            warning_threshold=Decimal("0.8"),
            critical_threshold=Decimal("0.95"),
        )

        # Недельный лимит потерь
        self.limit_configs[RiskLimitType.WEEKLY_LOSS] = LimitConfiguration(
            limit_type=RiskLimitType.WEEKLY_LOSS,
            limit_value=Decimal(str(self.config.weekly_loss_limit)),
            reset_period=LimitResetPeriod.WEEKLY,
            warning_threshold=Decimal("0.8"),
            critical_threshold=Decimal("0.95"),
        )

        # Лимит максимальных позиций
        self.limit_configs[RiskLimitType.MAX_CONCURRENT] = LimitConfiguration(
            limit_type=RiskLimitType.MAX_CONCURRENT,
            limit_value=Decimal(str(self.config.max_concurrent_positions)),
            reset_period=LimitResetPeriod.NEVER,
            warning_threshold=Decimal("0.8"),
            critical_threshold=Decimal("0.95"),
        )

        # Лимит максимальной корреляции
        self.limit_configs[RiskLimitType.MAX_CORRELATION] = LimitConfiguration(
            limit_type=RiskLimitType.MAX_CORRELATION,
            limit_value=Decimal("0.7"),
            reset_period=LimitResetPeriod.NEVER,
            warning_threshold=Decimal("0.8"),
            critical_threshold=Decimal("0.95"),
        )

        # Инициализация состояний лимитов
        for limit_type, config in self.limit_configs.items():
            self.limit_states[limit_type] = LimitState(
                limit_id=UUID("00000000-0000-0000-0000-000000000001"),
                current_value=Decimal("0.0"),
                last_reset=datetime.utcnow(),
                next_reset=self._calculate_next_reset(config.reset_period),
                status=LimitStatus.ACTIVE,
            )

    def _calculate_next_reset(self, reset_period: LimitResetPeriod) -> datetime | None:
        """Расчет времени следующего сброса"""
        now = datetime.utcnow()

        if reset_period == LimitResetPeriod.DAILY:
            # Сброс в 00:00 следующего дня
            tomorrow = now + timedelta(days=1)
            return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

        if reset_period == LimitResetPeriod.WEEKLY:
            # Сброс в понедельник
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = now + timedelta(days=days_until_monday)
            return next_monday.replace(hour=0, minute=0, second=0, microsecond=0)

        if reset_period == LimitResetPeriod.MONTHLY:
            # Сброс в первый день следующего месяца
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            return next_month.replace(hour=0, minute=0, second=0, microsecond=0)

        return None  # Никогда не сбрасывается

    def check_trade_allowed(
        self, symbol: str, position_value: Decimal, expected_pnl: Decimal
    ) -> tuple[bool, list[str]]:
        """
        Проверка возможности открытия сделки

        Args:
            symbol: Символ инструмента
            position_value: Стоимость позиции
            expected_pnl: Ожидаемый PnL (может быть отрицательным)

        Returns:
            (разрешена_ли_сделка, список_ошибок)
        """
        errors = []

        # Проверка кулдаунов
        if not self.cooldown_limits.can_trade():
            remaining = self.cooldown_limits.get_remaining_cooldown()
            errors.append(f"Cooldown active, {remaining}s remaining")

        # Проверка дневных лимитов
        if self.daily_limits.is_new_day():
            self.daily_limits.reset_for_new_day()

        # Проверка недельных лимитов
        if self.weekly_limits.is_new_week():
            self.weekly_limits.reset_for_new_week()

        # Проверка лимита позиций
        if not self.position_limits.can_add_position(position_value):
            errors.append(
                f"Cannot add position: {self.position_limits.current_positions}/{self.position_limits.max_positions} positions"
            )

        # Проверка дневного лимита потерь
        daily_loss_after_trade = abs(self.daily_limits.daily_loss + expected_pnl)
        daily_limit = self.limit_configs[RiskLimitType.DAILY_LOSS].limit_value
        if daily_loss_after_trade > daily_limit:
            errors.append(
                f"Daily loss limit would be exceeded: {daily_loss_after_trade} > {daily_limit}"
            )

        # Проверка недельного лимита потерь
        weekly_loss_after_trade = abs(self.weekly_limits.weekly_loss + expected_pnl)
        weekly_limit = self.limit_configs[RiskLimitType.WEEKLY_LOSS].limit_value
        if weekly_loss_after_trade > weekly_limit:
            errors.append(
                f"Weekly loss limit would be exceeded: {weekly_loss_after_trade} > {weekly_limit}"
            )

        # Проверка корреляции
        if not self.correlation_limits.check_correlation_limit(
            symbol, list(self.position_limits.position_symbols)
        ):
            errors.append(f"Correlation limit exceeded for symbol {symbol}")

        allowed = len(errors) == 0
        # persist metric
        try:
            if self._db_client:
                labels = {"symbol": symbol}
                self._fire_and_forget(
                    self._db_client.add_metric(
                        None,
                        "limits_check_allowed",
                        Decimal("1") if allowed else Decimal("0"),
                        labels,
                    )
                )
        except Exception:
            pass
        return allowed, errors

    def record_trade(
        self,
        symbol: str,
        position_value: Decimal,
        actual_pnl: Decimal,
        volume: Decimal,
        fees: Decimal,
    ) -> list[RiskViolation]:
        """
        Запись завершенной сделки

        Args:
            symbol: Символ инструмента
            position_value: Стоимость позиции
            actual_pnl: Фактический PnL
            volume: Объем сделки
            fees: Комиссии

        Returns:
            Список нарушений лимитов
        """
        violations = []

        # Обновляем дневные лимиты
        self.daily_limits.add_trade(actual_pnl, volume, fees)

        # Обновляем недельные лимиты
        self.weekly_limits.add_trade(actual_pnl, volume, fees)

        # Обновляем кулдауны
        self.cooldown_limits.record_trade(actual_pnl)

        # Обновляем позиции
        if actual_pnl > 0:  # Прибыльная сделка - закрываем позицию
            self.position_limits.remove_position(symbol, position_value)
        else:  # Убыточная сделка - добавляем позицию
            self.position_limits.add_position(symbol, position_value)

        # Проверяем нарушения лимитов
        violations.extend(self._check_limit_violations())
        # persist violations
        try:
            if self._db_client:
                for v in violations:
                    ctx = (
                        v.context
                        if isinstance(v.context, dict)
                        else {"context": str(v.context)}
                    )
                    self._fire_and_forget(
                        self._db_client.add_violation(
                            "limits",
                            v.violation_type,
                            f"{v.violation_value} > {v.limit_value}",
                            "high",
                            ctx,
                        )
                    )
        except Exception:
            pass

        # Добавляем нарушения в историю
        self.violations.extend(violations)

        return violations

    # --- Persistence helper ---
    def _fire_and_forget(self, coro):
        if coro is None:
            return
        try:
            import asyncio

            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            pass

    def _check_limit_violations(self) -> list[RiskViolation]:
        """Проверка нарушений лимитов"""
        violations = []

        # Проверка дневного лимита потерь
        daily_config = self.limit_configs[RiskLimitType.DAILY_LOSS]
        daily_state = self.limit_states[RiskLimitType.DAILY_LOSS]
        daily_state.current_value = abs(self.daily_limits.daily_loss)

        if daily_state.is_exceeded(daily_config):
            violation = RiskViolation(
                limit_id=daily_state.limit_id,
                violation_type="daily_loss_exceeded",
                violation_value=daily_state.current_value,
                limit_value=daily_config.limit_value,
                context={
                    "symbol": "daily",
                    "timestamp": datetime.utcnow(),
                    "daily_trades": self.daily_limits.daily_trades,
                },
            )
            violations.append(violation)
            daily_state.status = LimitStatus.EXCEEDED
            daily_state.violation_count += 1
            daily_state.last_violation = datetime.utcnow()

        # Проверка недельного лимита потерь
        weekly_config = self.limit_configs[RiskLimitType.WEEKLY_LOSS]
        weekly_state = self.limit_states[RiskLimitType.WEEKLY_LOSS]
        weekly_state.current_value = abs(self.weekly_limits.weekly_loss)

        if weekly_state.is_exceeded(weekly_config):
            violation = RiskViolation(
                limit_id=weekly_state.limit_id,
                violation_type="weekly_loss_exceeded",
                violation_value=weekly_state.current_value,
                limit_value=weekly_config.limit_value,
                context={
                    "symbol": "weekly",
                    "timestamp": datetime.utcnow(),
                    "weekly_trades": self.weekly_limits.weekly_trades,
                },
            )
            violations.append(violation)
            weekly_state.status = LimitStatus.EXCEEDED
            weekly_state.violation_count += 1
            weekly_state.last_violation = datetime.utcnow()

        # Проверка лимита позиций
        position_config = self.limit_configs[RiskLimitType.MAX_CONCURRENT]
        position_state = self.limit_states[RiskLimitType.MAX_CONCURRENT]
        position_state.current_value = Decimal(
            str(self.position_limits.current_positions)
        )

        if position_state.is_exceeded(position_config):
            violation = RiskViolation(
                limit_id=position_state.limit_id,
                violation_type="max_positions_exceeded",
                violation_value=position_state.current_value,
                limit_value=position_config.limit_value,
                context={
                    "symbol": "positions",
                    "timestamp": datetime.utcnow(),
                    "position_symbols": list(self.position_limits.position_symbols),
                },
            )
            violations.append(violation)
            position_state.status = LimitStatus.EXCEEDED
            position_state.violation_count += 1
            position_state.last_violation = datetime.utcnow()

        return violations

    def reset_limits(self, limit_types: list[RiskLimitType] | None = None):
        """Сброс лимитов"""
        if limit_types is None:
            limit_types = list(self.limit_configs.keys())

        for limit_type in limit_types:
            if limit_type in self.limit_states:
                state = self.limit_states[limit_type]
                config = self.limit_configs[limit_type]

                if state.should_reset(config):
                    state.current_value = Decimal("0.0")
                    state.last_reset = datetime.utcnow()
                    state.next_reset = self._calculate_next_reset(config.reset_period)
                    state.status = LimitStatus.ACTIVE
                    state.updated_at = datetime.utcnow()

                    self.logger.info(f"Reset limit {limit_type.value}")

    def get_limits_snapshot(self) -> LimitsSnapshot:
        """Получение снимка состояния всех лимитов"""
        return LimitsSnapshot(
            timestamp=datetime.utcnow(),
            daily_limits=self.daily_limits,
            weekly_limits=self.weekly_limits,
            position_limits=self.position_limits,
            correlation_limits=self.correlation_limits,
            cooldown_limits=self.cooldown_limits,
            violations=self.violations.copy(),
        )

    def get_limit_status(self, limit_type: RiskLimitType) -> dict[str, Any]:
        """Получение статуса конкретного лимита"""
        if limit_type not in self.limit_states:
            return {}

        state = self.limit_states[limit_type]
        config = self.limit_configs[limit_type]

        return {
            "limit_type": limit_type.value,
            "limit_value": float(config.limit_value),
            "current_value": float(state.current_value),
            "usage_percentage": state.get_usage_percentage(config),
            "remaining": float(state.get_remaining(config)),
            "status": state.status.value,
            "is_warning": state.is_warning_threshold_reached(config),
            "is_critical": state.is_critical_threshold_reached(config),
            "is_exceeded": state.is_exceeded(config),
            "violation_count": state.violation_count,
            "last_violation": state.last_violation,
            "next_reset": state.next_reset,
        }

    def get_all_limits_status(self) -> dict[str, dict[str, Any]]:
        """Получение статуса всех лимитов"""
        return {
            limit_type.value: self.get_limit_status(limit_type)
            for limit_type in self.limit_states
        }

    def add_correlation(self, symbol1: str, symbol2: str, correlation: float):
        """Добавление корреляции между символами"""
        self.correlation_limits.add_correlation(symbol1, symbol2, correlation)

    def update_limit_config(self, limit_type: RiskLimitType, **kwargs):
        """Обновление конфигурации лимита"""
        if limit_type in self.limit_configs:
            config = self.limit_configs[limit_type]
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            config.updated_at = datetime.utcnow()
            self.logger.info(f"Updated limit config for {limit_type.value}")

    def get_violations_summary(self) -> dict[str, Any]:
        """Получение сводки по нарушениям"""
        if not self.violations:
            return {"total_violations": 0}

        # Группируем по типам
        by_type = {}
        for violation in self.violations:
            violation_type = violation.violation_type
            if violation_type not in by_type:
                by_type[violation_type] = []
            by_type[violation_type].append(violation)

        # Статистика
        total_violations = len(self.violations)
        critical_violations = sum(
            1 for v in self.violations if v.get_severity() == "critical"
        )
        recent_violations = sum(
            1 for v in self.violations if (datetime.utcnow() - v.created_at).days <= 1
        )

        return {
            "total_violations": total_violations,
            "critical_violations": critical_violations,
            "recent_violations": recent_violations,
            "by_type": {k: len(v) for k, v in by_type.items()},
            "last_violation": (
                max(v.created_at for v in self.violations) if self.violations else None
            ),
        }
