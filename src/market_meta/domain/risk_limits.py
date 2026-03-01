"""
Управление лимитами риска для торговых позиций.

Содержит:
- Лимиты позиций по инструментам
- Общие лимиты риска
- Валидацию новых позиций
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from ..infrastructure.logging_config import get_logger
from .metadata import MarketMetadata

logger = get_logger("risk_limits")


class RiskLevel(Enum):
    """Уровни риска"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class PositionLimit:
    """Лимит позиции для инструмента"""

    symbol: str
    max_quantity: Decimal
    max_notional_value: Decimal
    max_position_size_pct: Decimal  # % от баланса
    risk_level: RiskLevel = RiskLevel.MEDIUM

    def validate_position(
        self, quantity: float, price: float, account_balance: float
    ) -> bool:
        """Проверяет, не превышает ли позиция лимиты"""
        if abs(quantity) > float(self.max_quantity):
            return False

        notional_value = abs(quantity) * price
        if notional_value > float(self.max_notional_value):
            return False

        position_pct = notional_value / account_balance
        if position_pct > float(self.max_position_size_pct):
            return False

        return True


@dataclass
class RiskLimits:
    """Лимиты риска для аккаунта"""

    # Общие лимиты
    max_total_exposure_pct: Decimal = Decimal("0.5")  # 50% от баланса
    max_daily_loss_pct: Decimal = Decimal("0.05")  # 5% дневной убыток
    max_drawdown_pct: Decimal = Decimal("0.15")  # 15% максимальная просадка

    # Лимиты по инструментам
    position_limits: dict[str, PositionLimit] = field(default_factory=dict)

    # Лимиты по типам инструментов
    max_spot_exposure_pct: Decimal = Decimal("0.3")  # 30% в спотах
    max_swap_exposure_pct: Decimal = Decimal("0.4")  # 40% в свопах
    max_futures_exposure_pct: Decimal = Decimal("0.3")  # 30% во фьючерсах

    # Временные лимиты
    max_positions_per_hour: int = 10
    max_positions_per_day: int = 50

    def add_position_limit(self, limit: PositionLimit):
        """Добавляет лимит позиции"""
        self.position_limits[limit.symbol] = limit

    def get_position_limit(self, symbol: str) -> PositionLimit | None:
        """Получает лимит позиции для символа"""
        return self.position_limits.get(symbol)

    def validate_total_exposure(
        self, positions: dict[str, dict[str, float]], account_balance: float
    ) -> bool:
        """Проверяет общую экспозицию"""
        total_exposure = sum(
            abs(pos.get("quantity", 0)) * pos.get("price", 0)
            for pos in positions.values()
        )

        exposure_pct = total_exposure / account_balance
        return exposure_pct <= float(self.max_total_exposure_pct)

    def validate_exposure_by_type(
        self,
        positions: dict[str, dict[str, float]],
        market_metadata: MarketMetadata,
        account_balance: float,
    ) -> dict[str, bool]:
        """Проверяет экспозицию по типам инструментов"""
        results = {}

        # Группируем позиции по типам
        spot_exposure = Decimal("0")
        swap_exposure = Decimal("0")
        futures_exposure = Decimal("0")

        for symbol, position_data in positions.items():
            instrument = market_metadata.get_instrument(symbol)
            if not instrument:
                continue

            notional_value = instrument.calculate_notional_value(
                position_data.get("price", 0), abs(position_data.get("quantity", 0))
            )

            if instrument.inst_type.value == "SPOT":
                spot_exposure += notional_value
            elif instrument.inst_type.value == "SWAP":
                swap_exposure += notional_value
            elif instrument.inst_type.value == "FUTURES":
                futures_exposure += notional_value

        # Проверяем лимиты
        results["spot"] = float(spot_exposure) / account_balance <= float(
            self.max_spot_exposure_pct
        )
        results["swap"] = float(swap_exposure) / account_balance <= float(
            self.max_swap_exposure_pct
        )
        results["futures"] = float(futures_exposure) / account_balance <= float(
            self.max_futures_exposure_pct
        )

        return results


@dataclass
class PositionLimits:
    """Управление лимитами позиций"""

    risk_limits: RiskLimits
    market_metadata: MarketMetadata

    # Трекинг позиций
    current_positions: dict[str, dict[str, float]] = field(default_factory=dict)
    position_history: list[dict[str, Any]] = field(default_factory=list)

    def add_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        timestamp: Any | None = None,
    ):
        """Добавляет позицию"""
        if timestamp is None:
            from datetime import datetime

            timestamp = datetime.now()

        self.current_positions[symbol] = {
            "quantity": quantity,
            "price": price,
            "timestamp": timestamp,
        }

        self.position_history.append(
            {
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp,
            }
        )

    def remove_position(self, symbol: str):
        """Удаляет позицию"""
        if symbol in self.current_positions:
            del self.current_positions[symbol]

    def validate_new_position(
        self, symbol: str, quantity: float, price: float, account_balance: float
    ) -> dict[str, bool]:
        """Валидирует новую позицию"""
        results = {}

        # Проверяем лимит позиции для конкретного символа
        position_limit = self.risk_limits.get_position_limit(symbol)
        if position_limit:
            results["position_limit"] = position_limit.validate_position(
                quantity, price, account_balance
            )
        else:
            results["position_limit"] = True

        # Проверяем общую экспозицию
        temp_positions = self.current_positions.copy()
        temp_positions[symbol] = {"quantity": quantity, "price": price}
        results["total_exposure"] = self.risk_limits.validate_total_exposure(
            temp_positions, account_balance
        )

        # Проверяем экспозицию по типам
        exposure_by_type = self.risk_limits.validate_exposure_by_type(
            temp_positions, self.market_metadata, account_balance
        )
        results.update(exposure_by_type)

        return results

    def get_position_summary(self) -> dict[str, Any]:
        """Получает сводку по позициям"""
        total_notional = Decimal("0")
        position_count = len(self.current_positions)

        for symbol, pos_data in self.current_positions.items():
            instrument = self.market_metadata.get_instrument(symbol)
            if instrument:
                notional = instrument.calculate_notional_value(
                    pos_data["price"], abs(pos_data["quantity"])
                )
                total_notional += notional

        return {
            "total_positions": position_count,
            "total_notional_value": float(total_notional),
            "positions": self.current_positions.copy(),
        }

    def get_risk_metrics(self, account_balance: float) -> dict[str, float]:
        """Получает метрики риска"""
        summary = self.get_position_summary()

        return {
            "total_exposure_pct": summary["total_notional_value"] / account_balance,
            "position_count": summary["total_positions"],
            "avg_position_size": (
                summary["total_notional_value"] / summary["total_positions"]
                if summary["total_positions"] > 0
                else 0
            ),
        }

    def check_risk_alerts(self, account_balance: float) -> list[str]:
        """Проверяет алерты риска"""
        alerts = []
        metrics = self.get_risk_metrics(account_balance)

        # Проверяем общую экспозицию
        if metrics["total_exposure_pct"] > float(
            self.risk_limits.max_total_exposure_pct
        ):
            alerts.append(
                f"High total exposure: {metrics['total_exposure_pct']:.2%} "
                f"(limit: {self.risk_limits.max_total_exposure_pct:.2%})"
            )

        # Проверяем количество позиций
        if metrics["position_count"] > self.risk_limits.max_positions_per_day:
            alerts.append(
                f"Too many positions: {metrics['position_count']} "
                f"(limit: {self.risk_limits.max_positions_per_day})"
            )

        return alerts
