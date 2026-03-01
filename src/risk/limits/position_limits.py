"""
Лимиты позиций

Управление лимитами позиций:
- Максимальное количество позиций
- Максимальный размер позиции
- Максимальная стоимость портфеля
- Контроль диверсификации
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from ..config import get_risk_config
from ..models import RiskConfig, RiskViolation
from .models import PositionLimitsState

logger = logging.getLogger(__name__)


class PositionLimits:
    """
    Управление лимитами позиций

    Основные функции:
    - Контроль количества открытых позиций
    - Ограничение размера отдельных позиций
    - Управление общей стоимостью портфеля
    - Отслеживание диверсификации
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние лимитов позиций
        self.state = PositionLimitsState(
            max_positions=self.config.max_concurrent_positions,
            max_position_value=Decimal(str(self.config.max_position_size_usdt)),
        )

        # Дополнительные лимиты
        self.max_portfolio_value = Decimal(
            "100000.0"
        )  # Максимальная стоимость портфеля
        self.min_position_value = Decimal("10.0")  # Минимальная стоимость позиции
        self.max_position_percentage = Decimal(
            "0.2"
        )  # Максимум 20% от портфеля на одну позицию

        # Пороги предупреждений
        self.warning_threshold = Decimal("0.8")  # 80% от лимита
        self.critical_threshold = Decimal("0.95")  # 95% от лимита

    def can_open_position(
        self,
        symbol: str,
        position_value: Decimal,
        portfolio_value: Decimal | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Проверка возможности открытия позиции

        Args:
            symbol: Символ инструмента
            position_value: Стоимость позиции
            portfolio_value: Общая стоимость портфеля

        Returns:
            (разрешена_ли_позиция, список_ошибок)
        """
        errors = []

        # Проверка максимального количества позиций
        if self.state.current_positions >= self.state.max_positions:
            errors.append(
                f"Maximum positions limit exceeded: {self.state.current_positions} >= {self.state.max_positions}"
            )

        # Проверка максимального размера позиции
        if position_value > self.state.max_position_value:
            errors.append(
                f"Position value exceeds maximum: {position_value} > {self.state.max_position_value}"
            )

        # Проверка минимального размера позиции
        if position_value < self.min_position_value:
            errors.append(
                f"Position value below minimum: {position_value} < {self.min_position_value}"
            )

        # Проверка общей стоимости портфеля
        if portfolio_value is not None:
            new_portfolio_value = self.state.total_position_value + position_value
            if new_portfolio_value > self.max_portfolio_value:
                errors.append(
                    f"Portfolio value would exceed maximum: {new_portfolio_value} > {self.max_portfolio_value}"
                )

            # Проверка максимального процента от портфеля
            position_percentage = position_value / portfolio_value
            if position_percentage > self.max_position_percentage:
                errors.append(
                    f"Position percentage exceeds maximum: {position_percentage:.2%} > {self.max_position_percentage:.2%}"
                )

        # Проверка дублирования символа
        if symbol in self.state.position_symbols:
            errors.append(f"Position already exists for symbol: {symbol}")

        return len(errors) == 0, errors

    def open_position(self, symbol: str, position_value: Decimal) -> bool:
        """
        Открытие позиции

        Args:
            symbol: Символ инструмента
            position_value: Стоимость позиции

        Returns:
            True если позиция успешно открыта
        """
        success = self.state.add_position(symbol, position_value)

        if success:
            self.logger.info(f"Opened position: {symbol}, value={position_value}")
        else:
            self.logger.warning(
                f"Failed to open position: {symbol}, value={position_value}"
            )

        return success

    def close_position(self, symbol: str, position_value: Decimal) -> bool:
        """
        Закрытие позиции

        Args:
            symbol: Символ инструмента
            position_value: Стоимость позиции

        Returns:
            True если позиция успешно закрыта
        """
        if symbol not in self.state.position_symbols:
            self.logger.warning(f"Position not found for symbol: {symbol}")
            return False

        self.state.remove_position(symbol, position_value)
        self.logger.info(f"Closed position: {symbol}, value={position_value}")
        return True

    def get_position_violations(self) -> list[RiskViolation]:
        """Получение нарушений лимитов позиций"""
        violations = []

        # Проверка превышения максимального количества позиций
        if self.state.current_positions > self.state.max_positions:
            violation = RiskViolation(
                limit_id=None,
                violation_type="max_positions_exceeded",
                violation_value=Decimal(str(self.state.current_positions)),
                limit_value=Decimal(str(self.state.max_positions)),
                context={
                    "symbol": "positions",
                    "timestamp": datetime.utcnow(),
                    "position_symbols": list(self.state.position_symbols),
                    "total_position_value": float(self.state.total_position_value),
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Maximum positions limit exceeded: {self.state.current_positions} > {self.state.max_positions}"
            )

        # Проверка превышения максимальной стоимости портфеля
        if self.state.total_position_value > self.max_portfolio_value:
            violation = RiskViolation(
                limit_id=None,
                violation_type="max_portfolio_value_exceeded",
                violation_value=self.state.total_position_value,
                limit_value=self.max_portfolio_value,
                context={
                    "symbol": "portfolio",
                    "timestamp": datetime.utcnow(),
                    "current_positions": self.state.current_positions,
                    "position_symbols": list(self.state.position_symbols),
                },
            )
            violations.append(violation)
            self.logger.warning(
                f"Maximum portfolio value exceeded: {self.state.total_position_value} > {self.max_portfolio_value}"
            )

        return violations

    def get_status(self) -> dict[str, Any]:
        """Получение статуса лимитов позиций"""
        return {
            "current_positions": self.state.current_positions,
            "max_positions": self.state.max_positions,
            "total_position_value": float(self.state.total_position_value),
            "max_position_value": float(self.state.max_position_value),
            "max_portfolio_value": float(self.max_portfolio_value),
            "min_position_value": float(self.min_position_value),
            "max_position_percentage": float(self.max_position_percentage),
            "position_symbols": list(self.state.position_symbols),
            "positions_usage_percentage": self.state.current_positions
            / self.state.max_positions,
            "portfolio_usage_percentage": float(
                self.state.total_position_value / self.max_portfolio_value
            ),
            "is_warning": self._is_warning_threshold_reached(),
            "is_critical": self._is_critical_threshold_reached(),
            "is_exceeded": self._is_exceeded(),
        }

    def _is_warning_threshold_reached(self) -> bool:
        """Проверка достижения порога предупреждения"""
        return (
            self.state.current_positions
            >= self.state.max_positions * self.warning_threshold
            or self.state.total_position_value
            >= self.max_portfolio_value * self.warning_threshold
        )

    def _is_critical_threshold_reached(self) -> bool:
        """Проверка достижения критического порога"""
        return (
            self.state.current_positions
            >= self.state.max_positions * self.critical_threshold
            or self.state.total_position_value
            >= self.max_portfolio_value * self.critical_threshold
        )

    def _is_exceeded(self) -> bool:
        """Проверка превышения лимитов"""
        return (
            self.state.current_positions > self.state.max_positions
            or self.state.total_position_value > self.max_portfolio_value
        )

    def get_remaining_limits(self) -> dict[str, Any]:
        """Получение оставшихся лимитов"""
        return {
            "remaining_positions": max(
                0, self.state.max_positions - self.state.current_positions
            ),
            "remaining_portfolio_value": float(
                max(
                    Decimal("0.0"),
                    self.max_portfolio_value - self.state.total_position_value,
                )
            ),
            "max_new_position_value": float(
                min(
                    self.state.max_position_value,
                    self.max_portfolio_value - self.state.total_position_value,
                )
            ),
        }

    def update_limits(
        self,
        max_positions: int | None = None,
        max_position_value: Decimal | None = None,
        max_portfolio_value: Decimal | None = None,
        min_position_value: Decimal | None = None,
        max_position_percentage: Decimal | None = None,
    ):
        """Обновление лимитов"""
        if max_positions is not None:
            self.state.max_positions = max_positions
        if max_position_value is not None:
            self.state.max_position_value = max_position_value
        if max_portfolio_value is not None:
            self.max_portfolio_value = max_portfolio_value
        if min_position_value is not None:
            self.min_position_value = min_position_value
        if max_position_percentage is not None:
            self.max_position_percentage = max_position_percentage

        self.logger.info(
            f"Updated position limits: max_positions={self.state.max_positions}, max_position_value={self.state.max_position_value}, max_portfolio_value={self.max_portfolio_value}"
        )

    def get_portfolio_summary(self) -> dict[str, Any]:
        """Получение сводки по портфелю"""
        return {
            "total_positions": self.state.current_positions,
            "total_value": float(self.state.total_position_value),
            "position_symbols": list(self.state.position_symbols),
            "avg_position_value": (
                float(self.state.total_position_value / self.state.current_positions)
                if self.state.current_positions > 0
                else 0.0
            ),
            "diversification_score": self._calculate_diversification_score(),
            "limits_status": self.get_status(),
        }

    def _calculate_diversification_score(self) -> float:
        """Расчет скора диверсификации (0-1, где 1 - максимальная диверсификация)"""
        if self.state.current_positions == 0:
            return 1.0

        # Простой расчет на основе количества позиций
        # В реальности можно добавить более сложную логику
        max_positions = self.state.max_positions
        current_positions = self.state.current_positions

        # Нормализуем к 0-1
        diversification_score = current_positions / max_positions

        return min(1.0, diversification_score)

    def get_position_analysis(self) -> dict[str, Any]:
        """Получение анализа позиций"""
        return {
            "position_count": self.state.current_positions,
            "total_value": float(self.state.total_position_value),
            "symbols": list(self.state.position_symbols),
            "diversification_score": self._calculate_diversification_score(),
            "concentration_risk": self._calculate_concentration_risk(),
            "limits_utilization": {
                "positions": self.state.current_positions / self.state.max_positions,
                "portfolio_value": float(
                    self.state.total_position_value / self.max_portfolio_value
                ),
            },
        }

    def _calculate_concentration_risk(self) -> float:
        """Расчет риска концентрации (0-1, где 1 - максимальный риск)"""
        if self.state.current_positions == 0:
            return 0.0

        # Простой расчет на основе количества позиций
        # Чем меньше позиций, тем выше риск концентрации
        concentration_risk = 1.0 - (
            self.state.current_positions / self.state.max_positions
        )

        return min(1.0, concentration_risk)

    def force_close_all_positions(self):
        """Принудительное закрытие всех позиций"""
        self.state.current_positions = 0
        self.state.total_position_value = Decimal("0.0")
        self.state.position_symbols.clear()
        self.state.updated_at = datetime.utcnow()

        self.logger.info("Force closed all positions")

    def get_position_by_symbol(self, symbol: str) -> dict[str, Any] | None:
        """Получение информации о позиции по символу"""
        if symbol not in self.state.position_symbols:
            return None

        # Здесь можно добавить более детальную информацию о позиции
        return {
            "symbol": symbol,
            "is_open": True,
            "opened_at": self.state.created_at,  # В реальности нужно хранить время открытия
        }
