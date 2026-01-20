"""
Лимиты кулдаунов

Управление кулдаунами:
- Кулдаун между сделками
- Кулдаун после убытков
- Кулдаун после нарушений лимитов
- Адаптивные кулдауны
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from ..config import get_risk_config
from ..models import RiskConfig, RiskViolation
from .models import CooldownLimitsState

logger = logging.getLogger(__name__)


class CooldownLimits:
    """
    Управление кулдаунами

    Основные функции:
    - Контроль времени между сделками
    - Кулдаун после убыточных сделок
    - Адаптивные кулдауны на основе производительности
    - Предотвращение overtrading
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние кулдаунов
        self.state = CooldownLimitsState(
            cooldown_between_trades_sec=self.config.cooldown_between_trades_sec,
            cooldown_after_loss_sec=self.config.cooldown_after_loss_sec,
        )

        # Дополнительные кулдауны
        self.cooldown_after_violation_sec = 3600  # 1 час после нарушения лимитов
        self.cooldown_after_high_loss_sec = 7200  # 2 часа после больших убытков
        self.cooldown_after_consecutive_losses_sec = (
            1800  # 30 минут после 3 убытков подряд
        )

        # Адаптивные параметры
        self.adaptive_cooldown_enabled = True
        self.performance_window_days = 7  # Окно для анализа производительности
        self.loss_threshold_for_high_loss = Decimal(
            "0.05"
        )  # 5% - порог для "большого убытка"
        self.consecutive_losses_threshold = 3  # Порог для последовательных убытков

        # История для адаптивных кулдаунов
        self.trade_history: list[dict[str, Any]] = []
        self.violation_history: list[dict[str, Any]] = []

    def can_trade(self) -> tuple[bool, list[str]]:
        """
        Проверка возможности торговли с учетом кулдаунов

        Returns:
            (разрешена_ли_торговля, список_ошибок)
        """
        errors = []

        # Проверка базового кулдауна между сделками
        if not self.state.can_trade():
            remaining = self.state.get_remaining_cooldown()
            errors.append(f"Cooldown active, {remaining}s remaining")

        # Проверка кулдауна после нарушений
        if self._is_violation_cooldown_active():
            remaining = self._get_violation_cooldown_remaining()
            errors.append(f"Violation cooldown active, {remaining}s remaining")

        # Проверка кулдауна после больших убытков
        if self._is_high_loss_cooldown_active():
            remaining = self._get_high_loss_cooldown_remaining()
            errors.append(f"High loss cooldown active, {remaining}s remaining")

        # Проверка кулдауна после последовательных убытков
        if self._is_consecutive_losses_cooldown_active():
            remaining = self._get_consecutive_losses_cooldown_remaining()
            errors.append(f"Consecutive losses cooldown active, {remaining}s remaining")

        return len(errors) == 0, errors

    def record_trade(
        self, pnl: Decimal, symbol: str, position_value: Decimal, volume: Decimal
    ) -> list[RiskViolation]:
        """
        Запись сделки для обновления кулдаунов

        Args:
            pnl: Фактический PnL
            symbol: Символ инструмента
            position_value: Стоимость позиции
            volume: Объем сделки

        Returns:
            Список нарушений
        """
        violations = []

        # Записываем в базовое состояние
        self.state.record_trade(pnl)

        # Добавляем в историю
        trade_record = {
            "timestamp": datetime.utcnow(),
            "symbol": symbol,
            "pnl": pnl,
            "position_value": position_value,
            "volume": volume,
            "is_loss": pnl < 0,
        }
        self.trade_history.append(trade_record)

        # Очищаем старую историю
        self._cleanup_old_history()

        # Проверяем необходимость дополнительных кулдаунов
        if pnl < 0:  # Убыточная сделка
            violations.extend(self._check_loss_cooldowns(pnl, symbol))

        # Адаптивные кулдауны
        if self.adaptive_cooldown_enabled:
            violations.extend(self._check_adaptive_cooldowns())

        self.logger.info(
            f"Recorded trade: {symbol}, PnL={pnl}, cooldown_remaining={self.state.get_remaining_cooldown()}"
        )

        return violations

    def record_violation(self, violation: RiskViolation):
        """
        Запись нарушения для активации кулдауна

        Args:
            violation: Нарушение лимитов
        """
        violation_record = {
            "timestamp": datetime.utcnow(),
            "violation_type": violation.violation_type,
            "severity": violation.get_severity(),
            "context": violation.context,
        }
        self.violation_history.append(violation_record)

        self.logger.warning(
            f"Recorded violation: {violation.violation_type}, severity={violation.get_severity()}"
        )

    def _check_loss_cooldowns(self, pnl: Decimal, symbol: str) -> list[RiskViolation]:
        """Проверка кулдаунов после убытков"""
        violations = []

        # Проверка большого убытка
        if abs(pnl) > self.loss_threshold_for_high_loss:
            violation = RiskViolation(
                limit_id=None,
                violation_type="high_loss_cooldown_activated",
                violation_value=abs(pnl),
                limit_value=self.loss_threshold_for_high_loss,
                context={
                    "symbol": symbol,
                    "timestamp": datetime.utcnow(),
                    "cooldown_duration": self.cooldown_after_high_loss_sec,
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"High loss cooldown activated: {pnl} > {self.loss_threshold_for_high_loss}"
            )

        # Проверка последовательных убытков
        consecutive_losses = self._count_consecutive_losses()
        if consecutive_losses >= self.consecutive_losses_threshold:
            violation = RiskViolation(
                limit_id=None,
                violation_type="consecutive_losses_cooldown_activated",
                violation_value=Decimal(str(consecutive_losses)),
                limit_value=Decimal(str(self.consecutive_losses_threshold)),
                context={
                    "symbol": symbol,
                    "timestamp": datetime.utcnow(),
                    "consecutive_losses": consecutive_losses,
                    "cooldown_duration": self.cooldown_after_consecutive_losses_sec,
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Consecutive losses cooldown activated: {consecutive_losses} >= {self.consecutive_losses_threshold}"
            )

        return violations

    def _check_adaptive_cooldowns(self) -> list[RiskViolation]:
        """Проверка адаптивных кулдаунов"""
        violations = []

        # Анализ производительности за последние дни
        performance = self._analyze_performance()

        # Адаптивный кулдаун на основе производительности
        if performance["loss_rate"] > 0.7:  # Более 70% убыточных сделок
            adaptive_cooldown = self._calculate_adaptive_cooldown(performance)
            if adaptive_cooldown > 0:
                violation = RiskViolation(
                    limit_id=None,
                    violation_type="adaptive_cooldown_activated",
                    violation_value=Decimal(str(performance["loss_rate"])),
                    limit_value=Decimal("0.7"),
                    context={
                        "timestamp": datetime.utcnow(),
                        "performance": performance,
                        "adaptive_cooldown": adaptive_cooldown,
                    },
                )
                violations.append(violation)
                self.logger.warning(
                    f"Adaptive cooldown activated: loss_rate={performance['loss_rate']:.2%}"
                )

        return violations

    def _is_violation_cooldown_active(self) -> bool:
        """Проверка активности кулдауна после нарушений"""
        if not self.violation_history:
            return False

        last_violation = max(self.violation_history, key=lambda x: x["timestamp"])
        time_since_violation = datetime.utcnow() - last_violation["timestamp"]

        return time_since_violation.total_seconds() < self.cooldown_after_violation_sec

    def _is_high_loss_cooldown_active(self) -> bool:
        """Проверка активности кулдауна после больших убытков"""
        if not self.trade_history:
            return False

        # Ищем последний большой убыток
        for trade in reversed(self.trade_history):
            if (
                trade["is_loss"]
                and abs(trade["pnl"]) > self.loss_threshold_for_high_loss
            ):
                time_since_loss = datetime.utcnow() - trade["timestamp"]
                return (
                    time_since_loss.total_seconds() < self.cooldown_after_high_loss_sec
                )

        return False

    def _is_consecutive_losses_cooldown_active(self) -> bool:
        """Проверка активности кулдауна после последовательных убытков"""
        consecutive_losses = self._count_consecutive_losses()

        if consecutive_losses >= self.consecutive_losses_threshold:
            # Находим время последнего убытка в серии
            last_loss_time = None
            for trade in reversed(self.trade_history):
                if trade["is_loss"]:
                    last_loss_time = trade["timestamp"]
                else:
                    break

            if last_loss_time:
                time_since_last_loss = datetime.utcnow() - last_loss_time
                return (
                    time_since_last_loss.total_seconds()
                    < self.cooldown_after_consecutive_losses_sec
                )

        return False

    def _get_violation_cooldown_remaining(self) -> int:
        """Получение оставшегося времени кулдауна после нарушений"""
        if not self.violation_history:
            return 0

        last_violation = max(self.violation_history, key=lambda x: x["timestamp"])
        time_since_violation = datetime.utcnow() - last_violation["timestamp"]
        remaining = (
            self.cooldown_after_violation_sec - time_since_violation.total_seconds()
        )

        return max(0, int(remaining))

    def _get_high_loss_cooldown_remaining(self) -> int:
        """Получение оставшегося времени кулдауна после больших убытков"""
        if not self.trade_history:
            return 0

        # Ищем последний большой убыток
        for trade in reversed(self.trade_history):
            if (
                trade["is_loss"]
                and abs(trade["pnl"]) > self.loss_threshold_for_high_loss
            ):
                time_since_loss = datetime.utcnow() - trade["timestamp"]
                remaining = (
                    self.cooldown_after_high_loss_sec - time_since_loss.total_seconds()
                )
                return max(0, int(remaining))

        return 0

    def _get_consecutive_losses_cooldown_remaining(self) -> int:
        """Получение оставшегося времени кулдауна после последовательных убытков"""
        consecutive_losses = self._count_consecutive_losses()

        if consecutive_losses >= self.consecutive_losses_threshold:
            # Находим время последнего убытка в серии
            last_loss_time = None
            for trade in reversed(self.trade_history):
                if trade["is_loss"]:
                    last_loss_time = trade["timestamp"]
                else:
                    break

            if last_loss_time:
                time_since_last_loss = datetime.utcnow() - last_loss_time
                remaining = (
                    self.cooldown_after_consecutive_losses_sec
                    - time_since_last_loss.total_seconds()
                )
                return max(0, int(remaining))

        return 0

    def _count_consecutive_losses(self) -> int:
        """Подсчет последовательных убытков"""
        consecutive_losses = 0

        for trade in reversed(self.trade_history):
            if trade["is_loss"]:
                consecutive_losses += 1
            else:
                break

        return consecutive_losses

    def _analyze_performance(self) -> dict[str, Any]:
        """Анализ производительности за последние дни"""
        if not self.trade_history:
            return {
                "total_trades": 0,
                "profitable_trades": 0,
                "loss_rate": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": Decimal("0.0"),
            }

        # Фильтруем сделки за последние дни
        cutoff_date = datetime.utcnow() - timedelta(days=self.performance_window_days)
        recent_trades = [t for t in self.trade_history if t["timestamp"] >= cutoff_date]

        if not recent_trades:
            return {
                "total_trades": 0,
                "profitable_trades": 0,
                "loss_rate": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": Decimal("0.0"),
            }

        total_trades = len(recent_trades)
        profitable_trades = sum(1 for t in recent_trades if not t["is_loss"])
        total_pnl = sum(t["pnl"] for t in recent_trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else Decimal("0.0")
        loss_rate = (
            (total_trades - profitable_trades) / total_trades
            if total_trades > 0
            else 0.0
        )

        return {
            "total_trades": total_trades,
            "profitable_trades": profitable_trades,
            "loss_rate": loss_rate,
            "avg_pnl": float(avg_pnl),
            "total_pnl": float(total_pnl),
        }

    def _calculate_adaptive_cooldown(self, performance: dict[str, Any]) -> int:
        """Расчет адаптивного кулдауна на основе производительности"""
        loss_rate = performance["loss_rate"]

        # Базовый кулдаун увеличивается с ростом loss_rate
        if loss_rate > 0.9:  # Более 90% убытков
            return 7200  # 2 часа
        if loss_rate > 0.8:  # Более 80% убытков
            return 3600  # 1 час
        if loss_rate > 0.7:  # Более 70% убытков
            return 1800  # 30 минут
        return 0  # Нет дополнительного кулдауна

    def _cleanup_old_history(self):
        """Очистка старой истории"""
        cutoff_date = datetime.utcnow() - timedelta(
            days=self.performance_window_days * 2
        )

        # Очищаем историю сделок
        self.trade_history = [
            t for t in self.trade_history if t["timestamp"] >= cutoff_date
        ]

        # Очищаем историю нарушений
        self.violation_history = [
            v for v in self.violation_history if v["timestamp"] >= cutoff_date
        ]

    def get_status(self) -> dict[str, Any]:
        """Получение статуса кулдаунов"""
        return {
            "can_trade": self.state.can_trade(),
            "remaining_cooldown": self.state.get_remaining_cooldown(),
            "last_trade_time": self.state.last_trade_time,
            "last_loss_time": self.state.last_loss_time,
            "cooldown_between_trades_sec": self.state.cooldown_between_trades_sec,
            "cooldown_after_loss_sec": self.state.cooldown_after_loss_sec,
            "cooldown_after_violation_sec": self.cooldown_after_violation_sec,
            "cooldown_after_high_loss_sec": self.cooldown_after_high_loss_sec,
            "cooldown_after_consecutive_losses_sec": self.cooldown_after_consecutive_losses_sec,
            "adaptive_cooldown_enabled": self.adaptive_cooldown_enabled,
            "consecutive_losses": self._count_consecutive_losses(),
            "performance": self._analyze_performance(),
        }

    def update_limits(
        self,
        cooldown_between_trades_sec: int | None = None,
        cooldown_after_loss_sec: int | None = None,
        cooldown_after_violation_sec: int | None = None,
        cooldown_after_high_loss_sec: int | None = None,
        cooldown_after_consecutive_losses_sec: int | None = None,
    ):
        """Обновление лимитов кулдаунов"""
        if cooldown_between_trades_sec is not None:
            self.state.cooldown_between_trades_sec = cooldown_between_trades_sec
        if cooldown_after_loss_sec is not None:
            self.state.cooldown_after_loss_sec = cooldown_after_loss_sec
        if cooldown_after_violation_sec is not None:
            self.cooldown_after_violation_sec = cooldown_after_violation_sec
        if cooldown_after_high_loss_sec is not None:
            self.cooldown_after_high_loss_sec = cooldown_after_high_loss_sec
        if cooldown_after_consecutive_losses_sec is not None:
            self.cooldown_after_consecutive_losses_sec = (
                cooldown_after_consecutive_losses_sec
            )

        self.logger.info(
            f"Updated cooldown limits: between_trades={self.state.cooldown_between_trades_sec}, after_loss={self.state.cooldown_after_loss_sec}"
        )

    def force_reset_cooldowns(self):
        """Принудительный сброс всех кулдаунов"""
        self.state.last_trade_time = None
        self.state.last_loss_time = None
        self.trade_history.clear()
        self.violation_history.clear()

        self.logger.info("Force reset all cooldowns")

    def get_cooldown_summary(self) -> dict[str, Any]:
        """Получение сводки по кулдаунам"""
        return {
            "current_status": self.get_status(),
            "trade_history_count": len(self.trade_history),
            "violation_history_count": len(self.violation_history),
            "consecutive_losses": self._count_consecutive_losses(),
            "performance_analysis": self._analyze_performance(),
        }
