"""
Модели для модуля расчета размеров позиций

Расширяет базовые модели из risk/models.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from ..models import PositionSizeRequest, PositionSizeResult


@dataclass
class SizingContext:
    """Контекст для расчета размера позиции"""

    symbol: str
    market_conditions: dict[str, Any] = field(default_factory=dict)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    risk_profile: dict[str, Any] = field(default_factory=dict)
    current_portfolio: dict[str, Any] = field(default_factory=dict)

    def get_market_volatility(self) -> float:
        """Получение волатильности рынка"""
        return self.market_conditions.get("volatility", 0.02)  # 2% по умолчанию

    def get_correlation_risk(self) -> float:
        """Получение риска корреляции"""
        return self.current_portfolio.get("correlation_risk", 0.0)

    def get_user_risk_tolerance(self) -> str:
        """Получение толерантности к риску пользователя"""
        return self.user_preferences.get(
            "risk_tolerance", "medium"
        )  # low, medium, high


@dataclass
class SizingConstraints:
    """Ограничения для расчета размера позиции"""

    max_position_size_usdt: Decimal = Decimal("10000.0")
    max_leverage: Decimal = Decimal("20.0")
    min_position_size_usdt: Decimal = Decimal("10.0")
    max_risk_per_trade: Decimal = Decimal("0.05")  # 5%
    max_portfolio_risk: Decimal = Decimal("0.20")  # 20%
    correlation_limit: Decimal = Decimal("0.7")  # 70%

    def validate(self):
        """Валидация ограничений"""
        if self.max_position_size_usdt <= 0:
            raise ValueError("max_position_size_usdt must be positive")

        if self.max_leverage <= 0:
            raise ValueError("max_leverage must be positive")

        if not 0 < self.max_risk_per_trade <= 1:
            raise ValueError("max_risk_per_trade must be between 0 and 1")


@dataclass
class SizingResult:
    """Расширенный результат расчета размера позиции"""

    base_result: PositionSizeResult
    sizing_context: SizingContext
    constraints: SizingConstraints
    adjustments_applied: list[str] = field(default_factory=list)
    risk_metrics: dict[str, Any] = field(default_factory=dict)
    portfolio_impact: dict[str, Any] = field(default_factory=dict)

    def get_total_risk(self) -> Decimal:
        """Получение общего риска позиции"""
        return self.base_result.risk_amount

    def get_portfolio_risk_contribution(self) -> Decimal:
        """Получение вклада в риск портфеля"""
        return self.portfolio_impact.get("risk_contribution", Decimal("0.0"))

    def is_within_limits(self) -> bool:
        """Проверка соответствия лимитам"""
        return (
            self.base_result.position_value <= self.constraints.max_position_size_usdt
            and self.base_result.leverage_used <= self.constraints.max_leverage
            and self.base_result.risk_amount <= self.constraints.max_risk_per_trade
        )


@dataclass
class SizingStrategy:
    """Стратегия расчета размера позиции"""

    name: str
    risk_method: str  # fixed_amount, percentage, kelly, volatility_adjusted
    position_sizing_method: str  # equal_weight, risk_parity, momentum
    rebalancing_frequency: str  # daily, weekly, monthly
    parameters: dict[str, Any] = field(default_factory=dict)

    def get_risk_multiplier(self, volatility: float) -> float:
        """Получение множителя риска на основе волатильности"""
        if self.risk_method == "volatility_adjusted":
            # Обратная корреляция с волатильностью
            base_risk = self.parameters.get("base_risk", 0.02)
            vol_adjustment = self.parameters.get("vol_adjustment", 0.5)
            return base_risk * (1 - vol_adjustment * volatility)
        return self.parameters.get("fixed_risk", 0.02)


@dataclass
class SizingHistory:
    """История расчетов размера позиции"""

    id: UUID = field(default_factory=uuid4)
    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request: PositionSizeRequest = None
    result: SizingResult = None
    strategy_used: str = ""
    performance_metrics: dict[str, Any] = field(default_factory=dict)

    def get_actual_vs_expected(self) -> dict[str, Any]:
        """Сравнение фактических и ожидаемых результатов"""
        return {
            "expected_return": self.performance_metrics.get("expected_return", 0.0),
            "actual_return": self.performance_metrics.get("actual_return", 0.0),
            "expected_risk": self.performance_metrics.get("expected_risk", 0.0),
            "actual_risk": self.performance_metrics.get("actual_risk", 0.0),
            "accuracy": self.performance_metrics.get("accuracy", 0.0),
        }
