"""
Недельные лимиты риска

Управление недельными лимитами:
- Недельные потери
- Количество сделок в неделю
- Объем торгов в неделю
- Комиссии за неделю
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from ..config import get_risk_config
from ..models import RiskConfig, RiskViolation
from .models import WeeklyLimitsState

logger = logging.getLogger(__name__)


class WeeklyLimits:
    """
    Управление недельными лимитами риска

    Основные функции:
    - Отслеживание недельных потерь
    - Контроль количества сделок в неделю
    - Мониторинг объема торгов в неделю
    - Автоматический сброс в понедельник
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние недельных лимитов
        self.state = WeeklyLimitsState(week_start=datetime.utcnow())

        # Конфигурация лимитов
        self.loss_limit = Decimal(str(self.config.weekly_loss_limit))
        self.max_trades = 500  # Максимум сделок в неделю
        self.max_volume = Decimal("5000000.0")  # Максимум объема в неделю
        self.max_fees = Decimal("5000.0")  # Максимум комиссий в неделю

        # Пороги предупреждений
        self.warning_threshold = Decimal("0.8")  # 80% от лимита
        self.critical_threshold = Decimal("0.95")  # 95% от лимита

    def check_new_week(self) -> bool:
        """Проверка начала новой недели"""
        if self.state.is_new_week():
            self.logger.info("New week detected, resetting weekly limits")
            self.state.reset_for_new_week()
            return True
        return False

    def can_trade(
        self, expected_pnl: Decimal, volume: Decimal, fees: Decimal
    ) -> tuple[bool, list[str]]:
        """
        Проверка возможности торговли с учетом недельных лимитов

        Args:
            expected_pnl: Ожидаемый PnL (может быть отрицательным)
            volume: Объем сделки
            fees: Комиссии

        Returns:
            (разрешена_ли_торговля, список_ошибок)
        """
        errors = []

        # Проверяем новую неделю
        self.check_new_week()

        # Проверка недельных потерь
        weekly_loss_after_trade = abs(self.state.weekly_loss + expected_pnl)
        if weekly_loss_after_trade > self.loss_limit:
            errors.append(
                f"Weekly loss limit would be exceeded: {weekly_loss_after_trade} > {self.loss_limit}"
            )

        # Проверка количества сделок
        if self.state.weekly_trades >= self.max_trades:
            errors.append(
                f"Weekly trades limit exceeded: {self.state.weekly_trades} >= {self.max_trades}"
            )

        # Проверка объема
        weekly_volume_after_trade = self.state.weekly_volume + volume
        if weekly_volume_after_trade > self.max_volume:
            errors.append(
                f"Weekly volume limit would be exceeded: {weekly_volume_after_trade} > {self.max_volume}"
            )

        # Проверка комиссий
        weekly_fees_after_trade = self.state.weekly_fees + fees
        if weekly_fees_after_trade > self.max_fees:
            errors.append(
                f"Weekly fees limit would be exceeded: {weekly_fees_after_trade} > {self.max_fees}"
            )

        return len(errors) == 0, errors

    def record_trade(
        self, pnl: Decimal, volume: Decimal, fees: Decimal
    ) -> list[RiskViolation]:
        """
        Запись сделки в недельные лимиты

        Args:
            pnl: Фактический PnL
            volume: Объем сделки
            fees: Комиссии

        Returns:
            Список нарушений лимитов
        """
        violations = []

        # Проверяем новую неделю
        self.check_new_week()

        # Записываем сделку
        self.state.add_trade(pnl, volume, fees)

        # Проверяем нарушения
        violations.extend(self._check_violations())

        self.logger.info(
            f"Recorded trade: PnL={pnl}, Volume={volume}, Fees={fees}. "
            f"Weekly totals: Loss={self.state.weekly_loss}, Trades={self.state.weekly_trades}, "
            f"Volume={self.state.weekly_volume}, Fees={self.state.weekly_fees}"
        )

        return violations

    def _check_violations(self) -> list[RiskViolation]:
        """Проверка нарушений недельных лимитов"""
        violations = []

        # Проверка лимита потерь
        if abs(self.state.weekly_loss) > self.loss_limit:
            violation = RiskViolation(
                limit_id=None,  # Будет установлен менеджером
                violation_type="weekly_loss_exceeded",
                violation_value=abs(self.state.weekly_loss),
                limit_value=self.loss_limit,
                context={
                    "symbol": "weekly",
                    "timestamp": datetime.utcnow(),
                    "weekly_trades": self.state.weekly_trades,
                    "weekly_volume": float(self.state.weekly_volume),
                    "weekly_fees": float(self.state.weekly_fees),
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Weekly loss limit exceeded: {abs(self.state.weekly_loss)} > {self.loss_limit}"
            )

        # Проверка лимита сделок
        if self.state.weekly_trades > self.max_trades:
            violation = RiskViolation(
                limit_id=None,
                violation_type="weekly_trades_exceeded",
                violation_value=Decimal(str(self.state.weekly_trades)),
                limit_value=Decimal(str(self.max_trades)),
                context={
                    "symbol": "weekly",
                    "timestamp": datetime.utcnow(),
                    "weekly_loss": float(self.state.weekly_loss),
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Weekly trades limit exceeded: {self.state.weekly_trades} > {self.max_trades}"
            )

        # Проверка лимита объема
        if self.state.weekly_volume > self.max_volume:
            violation = RiskViolation(
                limit_id=None,
                violation_type="weekly_volume_exceeded",
                violation_value=self.state.weekly_volume,
                limit_value=self.max_volume,
                context={
                    "symbol": "weekly",
                    "timestamp": datetime.utcnow(),
                    "weekly_trades": self.state.weekly_trades,
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Weekly volume limit exceeded: {self.state.weekly_volume} > {self.max_volume}"
            )

        # Проверка лимита комиссий
        if self.state.weekly_fees > self.max_fees:
            violation = RiskViolation(
                limit_id=None,
                violation_type="weekly_fees_exceeded",
                violation_value=self.state.weekly_fees,
                limit_value=self.max_fees,
                context={
                    "symbol": "weekly",
                    "timestamp": datetime.utcnow(),
                    "weekly_trades": self.state.weekly_trades,
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Weekly fees limit exceeded: {self.state.weekly_fees} > {self.max_fees}"
            )

        return violations

    def get_status(self) -> dict[str, Any]:
        """Получение статуса недельных лимитов"""
        return {
            "week_start": self.state.week_start.date(),
            "weekly_loss": float(self.state.weekly_loss),
            "weekly_trades": self.state.weekly_trades,
            "weekly_volume": float(self.state.weekly_volume),
            "weekly_fees": float(self.state.weekly_fees),
            "loss_limit": float(self.loss_limit),
            "max_trades": self.max_trades,
            "max_volume": float(self.max_volume),
            "max_fees": float(self.max_fees),
            "loss_usage_percentage": float(
                abs(self.state.weekly_loss) / self.loss_limit
            ),
            "trades_usage_percentage": self.state.weekly_trades / self.max_trades,
            "volume_usage_percentage": float(
                self.state.weekly_volume / self.max_volume
            ),
            "fees_usage_percentage": float(self.state.weekly_fees / self.max_fees),
            "is_warning": self._is_warning_threshold_reached(),
            "is_critical": self._is_critical_threshold_reached(),
            "is_exceeded": self._is_exceeded(),
        }

    def _is_warning_threshold_reached(self) -> bool:
        """Проверка достижения порога предупреждения"""
        return (
            abs(self.state.weekly_loss) >= self.loss_limit * self.warning_threshold
            or self.state.weekly_trades >= self.max_trades * self.warning_threshold
            or self.state.weekly_volume >= self.max_volume * self.warning_threshold
            or self.state.weekly_fees >= self.max_fees * self.warning_threshold
        )

    def _is_critical_threshold_reached(self) -> bool:
        """Проверка достижения критического порога"""
        return (
            abs(self.state.weekly_loss) >= self.loss_limit * self.critical_threshold
            or self.state.weekly_trades >= self.max_trades * self.critical_threshold
            or self.state.weekly_volume >= self.max_volume * self.critical_threshold
            or self.state.weekly_fees >= self.max_fees * self.critical_threshold
        )

    def _is_exceeded(self) -> bool:
        """Проверка превышения лимитов"""
        return (
            abs(self.state.weekly_loss) > self.loss_limit
            or self.state.weekly_trades > self.max_trades
            or self.state.weekly_volume > self.max_volume
            or self.state.weekly_fees > self.max_fees
        )

    def get_remaining_limits(self) -> dict[str, Any]:
        """Получение оставшихся лимитов"""
        return {
            "remaining_loss": float(
                max(Decimal("0.0"), self.loss_limit - abs(self.state.weekly_loss))
            ),
            "remaining_trades": max(0, self.max_trades - self.state.weekly_trades),
            "remaining_volume": float(
                max(Decimal("0.0"), self.max_volume - self.state.weekly_volume)
            ),
            "remaining_fees": float(
                max(Decimal("0.0"), self.max_fees - self.state.weekly_fees)
            ),
        }

    def update_limits(
        self,
        loss_limit: Decimal | None = None,
        max_trades: int | None = None,
        max_volume: Decimal | None = None,
        max_fees: Decimal | None = None,
    ):
        """Обновление лимитов"""
        if loss_limit is not None:
            self.loss_limit = loss_limit
        if max_trades is not None:
            self.max_trades = max_trades
        if max_volume is not None:
            self.max_volume = max_volume
        if max_fees is not None:
            self.max_fees = max_fees

        self.logger.info(
            f"Updated weekly limits: loss={self.loss_limit}, trades={self.max_trades}, volume={self.max_volume}, fees={self.max_fees}"
        )

    def force_reset(self):
        """Принудительный сброс недельных лимитов"""
        self.state.reset_for_new_week()
        self.logger.info("Force reset weekly limits")

    def get_weekly_summary(self) -> dict[str, Any]:
        """Получение сводки за неделю"""
        return {
            "week_start": self.state.week_start.date(),
            "total_pnl": float(self.state.weekly_loss),
            "total_trades": self.state.weekly_trades,
            "total_volume": float(self.state.weekly_volume),
            "total_fees": float(self.state.weekly_fees),
            "avg_trade_size": (
                float(self.state.weekly_volume / self.state.weekly_trades)
                if self.state.weekly_trades > 0
                else 0.0
            ),
            "avg_fee_per_trade": (
                float(self.state.weekly_fees / self.state.weekly_trades)
                if self.state.weekly_trades > 0
                else 0.0
            ),
            "limits_status": self.get_status(),
        }

    def get_weekly_trends(self) -> dict[str, Any]:
        """Получение трендов за неделю"""
        # Здесь можно добавить логику для анализа трендов
        # Пока возвращаем базовую информацию
        return {
            "week_start": self.state.week_start.date(),
            "total_pnl": float(self.state.weekly_loss),
            "total_trades": self.state.weekly_trades,
            "total_volume": float(self.state.weekly_volume),
            "total_fees": float(self.state.weekly_fees),
            "daily_avg_trades": self.state.weekly_trades / 7,
            "daily_avg_volume": float(self.state.weekly_volume / 7),
            "daily_avg_fees": float(self.state.weekly_fees / 7),
        }
