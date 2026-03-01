"""
Валидаторы для модуля расчета размеров позиций

Интегрируется с market_meta/validators.py для проверки рыночных данных
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from ..config import get_risk_config
from ..models import PositionSizeRequest, RiskConfig
from .models import SizingContext, SizingResult

logger = logging.getLogger(__name__)


class PositionSizeValidator:
    """
    Валидатор для расчета размера позиции

    Проверяет:
    - Корректность входных параметров
    - Соответствие лимитам и ограничениям
    - Качество рыночных данных
    - Риски позиции
    """

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Пороговые значения для валидации
        self.min_balance = Decimal("100.0")  # Минимальный баланс
        self.min_price = Decimal("0.0001")  # Минимальная цена
        self.max_price = Decimal("1000000.0")  # Максимальная цена
        self.min_stop_distance = Decimal(
            "0.001"
        )  # 0.1% минимальное расстояние до стопа
        self.max_stop_distance = Decimal("0.20")  # 20% максимальное расстояние до стопа

    def validate_request(self, request: PositionSizeRequest) -> list[str]:
        """
        Валидация запроса на расчет размера позиции

        Args:
            request: Запрос на расчет размера позиции

        Returns:
            Список ошибок валидации
        """
        errors = []

        try:
            # Базовая валидация
            request.validate()
        except ValueError as e:
            errors.append(str(e))
            return errors

        # Проверка баланса
        if request.balance < self.min_balance:
            errors.append(f"Balance {request.balance} below minimum {self.min_balance}")

        # Проверка цены входа
        if not (self.min_price <= request.entry_price <= self.max_price):
            errors.append(
                f"Entry price {request.entry_price} out of range [{self.min_price}, {self.max_price}]"
            )

        # Проверка цены стопа
        if not (self.min_price <= request.stop_price <= self.max_price):
            errors.append(
                f"Stop price {request.stop_price} out of range [{self.min_price}, {self.max_price}]"
            )

        # Проверка расстояния до стопа
        stop_distance = (
            abs(request.entry_price - request.stop_price) / request.entry_price
        )
        if stop_distance < self.min_stop_distance:
            errors.append(
                f"Stop distance {stop_distance:.4f} below minimum {self.min_stop_distance}"
            )
        elif stop_distance > self.max_stop_distance:
            errors.append(
                f"Stop distance {stop_distance:.4f} above maximum {self.max_stop_distance}"
            )

        # Проверка риска на сделку
        if request.risk_per_trade > self.config.max_risk_per_trade:
            errors.append(
                f"Risk per trade {request.risk_per_trade} exceeds maximum {self.config.max_risk_per_trade}"
            )

        # Проверка размера лота
        if request.lot_size <= 0:
            errors.append(f"Lot size {request.lot_size} must be positive")

        # Проверка максимального плеча
        if request.max_leverage <= 0:
            errors.append(f"Max leverage {request.max_leverage} must be positive")

        # Проверка количества текущих позиций
        if request.current_positions < 0:
            errors.append(
                f"Current positions {request.current_positions} cannot be negative"
            )

        if request.current_positions >= request.max_concurrent:
            errors.append(
                f"Current positions {request.current_positions} at maximum {request.max_concurrent}"
            )

        return errors

    def validate_result(self, result: SizingResult) -> list[str]:
        """
        Валидация результата расчета размера позиции

        Args:
            result: Результат расчета размера позиции

        Returns:
            Список ошибок валидации
        """
        errors = []

        base_result = result.base_result

        # Проверка валидности базового результата
        if not base_result.is_valid:
            errors.extend(base_result.errors)
            return errors

        # Проверка размера позиции
        if base_result.position_size <= 0:
            errors.append("Position size must be positive")

        # Проверка стоимости позиции
        if base_result.position_value <= 0:
            errors.append("Position value must be positive")

        # Проверка суммы риска
        if base_result.risk_amount <= 0:
            errors.append("Risk amount must be positive")

        # Проверка плеча
        if base_result.leverage_used <= 0:
            errors.append("Leverage must be positive")

        if base_result.leverage_used > result.constraints.max_leverage:
            errors.append(
                f"Leverage {base_result.leverage_used} exceeds maximum {result.constraints.max_leverage}"
            )

        # Проверка требуемой маржи
        if base_result.margin_required <= 0:
            errors.append("Margin required must be positive")

        # Проверка расстояния до ликвидации
        if base_result.liquidation_distance <= 0:
            errors.append("Liquidation distance must be positive")

        if base_result.liquidation_distance > Decimal("0.5"):  # 50% максимум
            errors.append(
                f"Liquidation distance {base_result.liquidation_distance} too high (max 50%)"
            )

        # Проверка соотношения риск/доходность
        if base_result.risk_reward_ratio <= 0:
            errors.append("Risk/reward ratio must be positive")

        if base_result.risk_reward_ratio < Decimal("1.0"):
            errors.append(
                f"Risk/reward ratio {base_result.risk_reward_ratio} below 1.0"
            )

        # Проверка соответствия ограничениям
        if not result.is_within_limits():
            errors.append("Result exceeds configured limits")

        return errors

    def validate_context(self, context: SizingContext) -> list[str]:
        """
        Валидация контекста расчета

        Args:
            context: Контекст расчета размера позиции

        Returns:
            Список ошибок валидации
        """
        errors = []

        # Проверка символа
        if not context.symbol or len(context.symbol) < 3:
            errors.append("Symbol must be at least 3 characters")

        # Проверка рыночных условий
        volatility = context.get_market_volatility()
        if not (0 <= volatility <= 1):
            errors.append(f"Market volatility {volatility} out of range [0, 1]")

        # Проверка риска корреляции
        correlation_risk = context.get_correlation_risk()
        if not (0 <= correlation_risk <= 1):
            errors.append(f"Correlation risk {correlation_risk} out of range [0, 1]")

        # Проверка толерантности к риску
        risk_tolerance = context.get_user_risk_tolerance()
        if risk_tolerance not in ["low", "medium", "high"]:
            errors.append(f"Invalid risk tolerance: {risk_tolerance}")

        # Проверка портфеля
        portfolio_value = context.current_portfolio.get("total_value", 0)
        if portfolio_value < 0:
            errors.append("Portfolio value cannot be negative")

        positions_count = context.current_portfolio.get("positions_count", 0)
        if positions_count < 0:
            errors.append("Positions count cannot be negative")

        return errors

    def validate_market_conditions(
        self, symbol: str, market_data: dict[str, Any]
    ) -> list[str]:
        """
        Валидация рыночных условий

        Args:
            symbol: Символ инструмента
            market_data: Рыночные данные

        Returns:
            Список ошибок валидации
        """
        errors = []

        # Проверка наличия основных данных
        required_fields = ["price", "volume", "spread", "liquidity"]
        for field in required_fields:
            if field not in market_data:
                errors.append(f"Missing market data field: {field}")

        # Проверка цены
        price = market_data.get("price", 0)
        if not (self.min_price <= price <= self.max_price):
            errors.append(
                f"Market price {price} out of range [{self.min_price}, {self.max_price}]"
            )

        # Проверка объема
        volume = market_data.get("volume", 0)
        if volume <= 0:
            errors.append(f"Market volume {volume} must be positive")

        # Проверка спреда
        spread = market_data.get("spread", 0)
        if spread < 0:
            errors.append(f"Market spread {spread} cannot be negative")

        if spread > 0.01:  # 1% максимум
            errors.append(f"Market spread {spread} too high (max 1%)")

        # Проверка ликвидности
        liquidity = market_data.get("liquidity", 0)
        if liquidity <= 0:
            errors.append(f"Market liquidity {liquidity} must be positive")

        # Проверка волатильности
        volatility = market_data.get("volatility", 0)
        if not (0 <= volatility <= 1):
            errors.append(f"Market volatility {volatility} out of range [0, 1]")

        return errors

    def validate_risk_limits(
        self, request: PositionSizeRequest, current_limits: dict[str, Any]
    ) -> list[str]:
        """
        Валидация лимитов риска

        Args:
            request: Запрос на расчет размера позиции
            current_limits: Текущие лимиты

        Returns:
            Список ошибок валидации
        """
        errors = []

        # Проверка дневного лимита потерь
        daily_loss = current_limits.get("daily_loss", 0)
        daily_limit = self.config.daily_loss_limit
        if daily_loss >= daily_limit:
            errors.append(f"Daily loss limit exceeded: {daily_loss} >= {daily_limit}")

        # Проверка недельного лимита потерь
        weekly_loss = current_limits.get("weekly_loss", 0)
        weekly_limit = self.config.weekly_loss_limit
        if weekly_loss >= weekly_limit:
            errors.append(
                f"Weekly loss limit exceeded: {weekly_loss} >= {weekly_limit}"
            )

        # Проверка максимального количества позиций
        current_positions = current_limits.get("current_positions", 0)
        max_positions = self.config.max_concurrent_positions
        if current_positions >= max_positions:
            errors.append(
                f"Maximum concurrent positions exceeded: {current_positions} >= {max_positions}"
            )

        # Проверка кулдауна
        last_trade_time = current_limits.get("last_trade_time")
        if last_trade_time:
            time_since_last_trade = datetime.utcnow() - last_trade_time
            cooldown = timedelta(seconds=self.config.cooldown_between_trades_sec)
            if time_since_last_trade < cooldown:
                remaining = cooldown - time_since_last_trade
                errors.append(
                    f"Cooldown period active, {remaining.total_seconds():.0f}s remaining"
                )

        return errors

    def validate_comprehensive(
        self,
        request: PositionSizeRequest,
        context: SizingContext,
        result: SizingResult,
        market_data: dict[str, Any] | None = None,
        current_limits: dict[str, Any] | None = None,
    ) -> dict[str, list[str]]:
        """
        Комплексная валидация всех компонентов

        Args:
            request: Запрос на расчет размера позиции
            context: Контекст расчета
            result: Результат расчета
            market_data: Рыночные данные
            current_limits: Текущие лимиты

        Returns:
            Словарь с ошибками по категориям
        """
        validation_results = {
            "request": [],
            "context": [],
            "result": [],
            "market": [],
            "limits": [],
        }

        # Валидация запроса
        validation_results["request"] = self.validate_request(request)

        # Валидация контекста
        validation_results["context"] = self.validate_context(context)

        # Валидация результата
        validation_results["result"] = self.validate_result(result)

        # Валидация рыночных данных
        if market_data:
            validation_results["market"] = self.validate_market_conditions(
                request.symbol, market_data
            )

        # Валидация лимитов
        if current_limits:
            validation_results["limits"] = self.validate_risk_limits(
                request, current_limits
            )

        return validation_results

    def is_valid(
        self,
        request: PositionSizeRequest,
        context: SizingContext,
        result: SizingResult,
        market_data: dict[str, Any] | None = None,
        current_limits: dict[str, Any] | None = None,
    ) -> bool:
        """
        Проверка общей валидности расчета

        Returns:
            True если все проверки пройдены
        """
        validation_results = self.validate_comprehensive(
            request, context, result, market_data, current_limits
        )

        # Проверяем, что нет ошибок ни в одной категории
        for category, errors in validation_results.items():
            if errors:
                self.logger.warning(f"Validation failed in {category}: {errors}")
                return False

        return True
