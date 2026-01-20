"""
Дневные лимиты риска

Управление дневными лимитами:
- Дневные потери
- Количество сделок в день
- Объем торгов в день
- Комиссии за день
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from ..config import get_risk_config
from ..models import RiskConfig, RiskViolation
from .models import DailyLimitsState

logger = logging.getLogger(__name__)


class DailyLimits:
    """
    Управление дневными лимитами риска

    Основные функции:
    - Отслеживание дневных потерь
    - Контроль количества сделок
    - Мониторинг объема торгов
    - Автоматический сброс в полночь
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние дневных лимитов
        self.state = DailyLimitsState(date=datetime.utcnow())

        # Конфигурация лимитов
        self.loss_limit = Decimal(str(self.config.daily_loss_limit))
        self.max_trades = 100  # Максимум сделок в день
        self.max_volume = Decimal("1000000.0")  # Максимум объема в день
        self.max_fees = Decimal("1000.0")  # Максимум комиссий в день

        # Пороги предупреждений
        self.warning_threshold = Decimal("0.8")  # 80% от лимита
        self.critical_threshold = Decimal("0.95")  # 95% от лимита

    def check_new_day(self) -> bool:
        """Проверка начала нового дня"""
        if self.state.is_new_day():
            self.logger.info("New day detected, resetting daily limits")
            self.state.reset_for_new_day()
            return True
        return False

    def can_trade(
        self, expected_pnl: Decimal, volume: Decimal, fees: Decimal
    ) -> tuple[bool, list[str]]:
        """
        Проверка возможности торговли с учетом дневных лимитов

        Args:
            expected_pnl: Ожидаемый PnL (может быть отрицательным)
            volume: Объем сделки
            fees: Комиссии

        Returns:
            (разрешена_ли_торговля, список_ошибок)
        """
        errors = []

        # Проверяем новый день
        self.check_new_day()

        # Проверка дневных потерь
        daily_loss_after_trade = abs(self.state.daily_loss + expected_pnl)
        if daily_loss_after_trade > self.loss_limit:
            errors.append(
                f"Daily loss limit would be exceeded: {daily_loss_after_trade} > {self.loss_limit}"
            )

        # Проверка количества сделок
        if self.state.daily_trades >= self.max_trades:
            errors.append(
                f"Daily trades limit exceeded: {self.state.daily_trades} >= {self.max_trades}"
            )

        # Проверка объема
        daily_volume_after_trade = self.state.daily_volume + volume
        if daily_volume_after_trade > self.max_volume:
            errors.append(
                f"Daily volume limit would be exceeded: {daily_volume_after_trade} > {self.max_volume}"
            )

        # Проверка комиссий
        daily_fees_after_trade = self.state.daily_fees + fees
        if daily_fees_after_trade > self.max_fees:
            errors.append(
                f"Daily fees limit would be exceeded: {daily_fees_after_trade} > {self.max_fees}"
            )

        return len(errors) == 0, errors

    def record_trade(
        self, pnl: Decimal, volume: Decimal, fees: Decimal
    ) -> list[RiskViolation]:
        """
        Запись сделки в дневные лимиты

        Args:
            pnl: Фактический PnL
            volume: Объем сделки
            fees: Комиссии

        Returns:
            Список нарушений лимитов
        """
        violations = []

        # Проверяем новый день
        self.check_new_day()

        # Записываем сделку
        self.state.add_trade(pnl, volume, fees)

        # Проверяем нарушения
        violations.extend(self._check_violations())

        self.logger.info(
            f"Recorded trade: PnL={pnl}, Volume={volume}, Fees={fees}. "
            f"Daily totals: Loss={self.state.daily_loss}, Trades={self.state.daily_trades}, "
            f"Volume={self.state.daily_volume}, Fees={self.state.daily_fees}"
        )

        return violations

    def _check_violations(self) -> list[RiskViolation]:
        """Проверка нарушений дневных лимитов"""
        violations = []

        # Проверка лимита потерь
        if abs(self.state.daily_loss) > self.loss_limit:
            violation = RiskViolation(
                limit_id=None,  # Будет установлен менеджером
                violation_type="daily_loss_exceeded",
                violation_value=abs(self.state.daily_loss),
                limit_value=self.loss_limit,
                context={
                    "symbol": "daily",
                    "timestamp": datetime.utcnow(),
                    "daily_trades": self.state.daily_trades,
                    "daily_volume": float(self.state.daily_volume),
                    "daily_fees": float(self.state.daily_fees),
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Daily loss limit exceeded: {abs(self.state.daily_loss)} > {self.loss_limit}"
            )

        # Проверка лимита сделок
        if self.state.daily_trades > self.max_trades:
            violation = RiskViolation(
                limit_id=None,
                violation_type="daily_trades_exceeded",
                violation_value=Decimal(str(self.state.daily_trades)),
                limit_value=Decimal(str(self.max_trades)),
                context={
                    "symbol": "daily",
                    "timestamp": datetime.utcnow(),
                    "daily_loss": float(self.state.daily_loss),
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Daily trades limit exceeded: {self.state.daily_trades} > {self.max_trades}"
            )

        # Проверка лимита объема
        if self.state.daily_volume > self.max_volume:
            violation = RiskViolation(
                limit_id=None,
                violation_type="daily_volume_exceeded",
                violation_value=self.state.daily_volume,
                limit_value=self.max_volume,
                context={
                    "symbol": "daily",
                    "timestamp": datetime.utcnow(),
                    "daily_trades": self.state.daily_trades,
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Daily volume limit exceeded: {self.state.daily_volume} > {self.max_volume}"
            )

        # Проверка лимита комиссий
        if self.state.daily_fees > self.max_fees:
            violation = RiskViolation(
                limit_id=None,
                violation_type="daily_fees_exceeded",
                violation_value=self.state.daily_fees,
                limit_value=self.max_fees,
                context={
                    "symbol": "daily",
                    "timestamp": datetime.utcnow(),
                    "daily_trades": self.state.daily_trades,
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Daily fees limit exceeded: {self.state.daily_fees} > {self.max_fees}"
            )

        return violations

    def get_status(self) -> dict[str, Any]:
        """Получение статуса дневных лимитов"""
        return {
            "date": self.state.date.date(),
            "daily_loss": float(self.state.daily_loss),
            "daily_trades": self.state.daily_trades,
            "daily_volume": float(self.state.daily_volume),
            "daily_fees": float(self.state.daily_fees),
            "last_trade_time": self.state.last_trade_time,
            "loss_limit": float(self.loss_limit),
            "max_trades": self.max_trades,
            "max_volume": float(self.max_volume),
            "max_fees": float(self.max_fees),
            "loss_usage_percentage": float(
                abs(self.state.daily_loss) / self.loss_limit
            ),
            "trades_usage_percentage": self.state.daily_trades / self.max_trades,
            "volume_usage_percentage": float(self.state.daily_volume / self.max_volume),
            "fees_usage_percentage": float(self.state.daily_fees / self.max_fees),
            "is_warning": self._is_warning_threshold_reached(),
            "is_critical": self._is_critical_threshold_reached(),
            "is_exceeded": self._is_exceeded(),
        }

    def _is_warning_threshold_reached(self) -> bool:
        """Проверка достижения порога предупреждения"""
        return (
            abs(self.state.daily_loss) >= self.loss_limit * self.warning_threshold
            or self.state.daily_trades >= self.max_trades * self.warning_threshold
            or self.state.daily_volume >= self.max_volume * self.warning_threshold
            or self.state.daily_fees >= self.max_fees * self.warning_threshold
        )

    def _is_critical_threshold_reached(self) -> bool:
        """Проверка достижения критического порога"""
        return (
            abs(self.state.daily_loss) >= self.loss_limit * self.critical_threshold
            or self.state.daily_trades >= self.max_trades * self.critical_threshold
            or self.state.daily_volume >= self.max_volume * self.critical_threshold
            or self.state.daily_fees >= self.max_fees * self.critical_threshold
        )

    def _is_exceeded(self) -> bool:
        """Проверка превышения лимитов"""
        return (
            abs(self.state.daily_loss) > self.loss_limit
            or self.state.daily_trades > self.max_trades
            or self.state.daily_volume > self.max_volume
            or self.state.daily_fees > self.max_fees
        )

    def get_remaining_limits(self) -> dict[str, Any]:
        """Получение оставшихся лимитов"""
        return {
            "remaining_loss": float(
                max(Decimal("0.0"), self.loss_limit - abs(self.state.daily_loss))
            ),
            "remaining_trades": max(0, self.max_trades - self.state.daily_trades),
            "remaining_volume": float(
                max(Decimal("0.0"), self.max_volume - self.state.daily_volume)
            ),
            "remaining_fees": float(
                max(Decimal("0.0"), self.max_fees - self.state.daily_fees)
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
            f"Updated daily limits: loss={self.loss_limit}, trades={self.max_trades}, volume={self.max_volume}, fees={self.max_fees}"
        )

    def force_reset(self):
        """Принудительный сброс дневных лимитов"""
        self.state.reset_for_new_day()
        self.logger.info("Force reset daily limits")

    def get_daily_summary(self) -> dict[str, Any]:
        """Получение сводки за день"""
        return {
            "date": self.state.date.date(),
            "total_pnl": float(self.state.daily_loss),
            "total_trades": self.state.daily_trades,
            "total_volume": float(self.state.daily_volume),
            "total_fees": float(self.state.daily_fees),
            "avg_trade_size": (
                float(self.state.daily_volume / self.state.daily_trades)
                if self.state.daily_trades > 0
                else 0.0
            ),
            "avg_fee_per_trade": (
                float(self.state.daily_fees / self.state.daily_trades)
                if self.state.daily_trades > 0
                else 0.0
            ),
            "last_trade_time": self.state.last_trade_time,
            "limits_status": self.get_status(),
        }
