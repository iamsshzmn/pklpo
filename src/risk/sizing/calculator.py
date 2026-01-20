"""
Калькулятор размера позиции с учетом рисков

Интегрируется с существующими модулями:
- positions/calculator.py - базовая логика расчета
- trade_recommender/position_model.py - управление рисками
- market_meta/validators.py - валидация рыночных данных
"""

import logging
from decimal import Decimal
from typing import Any

from ..config import get_risk_config
from ..database.client import RiskDatabaseClient
from ..models import PositionSizeRequest, PositionSizeResult, RiskConfig
from .models import SizingConstraints, SizingContext, SizingResult, SizingStrategy

logger = logging.getLogger(__name__)


class PositionSizeCalculator:
    """
    Калькулятор размера позиции с учетом рисков

    Основные функции:
    - Расчет размера позиции на основе риска
    - Учет комиссий и проскальзывания
    - Проверка лимитов и ограничений
    - Оптимизация плеча
    """

    def __init__(
        self,
        config: RiskConfig | None = None,
        db_client: RiskDatabaseClient | None = None,
    ):
        self.config = config or get_risk_config()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._db_client = db_client

        # Параметры для расчета
        self.min_risk_reward_ratio = Decimal(
            "1.5"
        )  # Минимальное соотношение риск/доходность
        self.max_risk_reward_ratio = Decimal(
            "3.0"
        )  # Максимальное соотношение риск/доходность

    def calculate_position_size(
        self,
        request: PositionSizeRequest,
        context: SizingContext | None = None,
        strategy: SizingStrategy | None = None,
    ) -> SizingResult:
        """
        Расчет размера позиции с учетом рисков

        Args:
            request: Запрос на расчет размера позиции
            context: Контекст расчета (рыночные условия, портфель)
            strategy: Стратегия расчета размера позиции

        Returns:
            SizingResult с результатами расчета
        """
        try:
            # Валидируем запрос
            request.validate()

            # Создаем контекст по умолчанию если не передан
            if context is None:
                context = SizingContext(symbol=request.symbol)

            # Создаем стратегию по умолчанию если не передана
            if strategy is None:
                strategy = self._create_default_strategy()

            # Создаем ограничения
            constraints = self._create_constraints(request)

            # Рассчитываем базовый размер позиции
            base_result = self._calculate_base_position_size(request, context, strategy)

            # Применяем ограничения и корректировки
            adjusted_result = self._apply_constraints_and_adjustments(
                base_result, request, context, constraints, strategy
            )

            # Рассчитываем метрики риска
            risk_metrics = self._calculate_risk_metrics(adjusted_result, context)

            # Рассчитываем влияние на портфель
            portfolio_impact = self._calculate_portfolio_impact(
                adjusted_result, context
            )

            # Создаем результат
            result = SizingResult(
                base_result=adjusted_result,
                sizing_context=context,
                constraints=constraints,
                risk_metrics=risk_metrics,
                portfolio_impact=portfolio_impact,
            )

            self.logger.info(
                f"Position size calculated for {request.symbol}: "
                f"size={adjusted_result.position_size}, "
                f"value={adjusted_result.position_value}, "
                f"risk={adjusted_result.risk_amount}, "
                f"leverage={adjusted_result.leverage_used}"
            )
            # persist sizing log (best-effort)
            try:
                if self._db_client:

                    async def write():
                        await self._db_client.add_sizing_log(
                            None,
                            adjusted_result.position_value
                            / max(Decimal("1e-9"), request.entry_price),
                            request.stop_price,
                            None,
                            request.balance,
                            request.risk_per_trade,
                            adjusted_result.position_size,
                            adjusted_result.position_value,
                            Decimal("0"),
                            Decimal("0"),
                            request.lot_size,
                            {
                                "symbol": request.symbol,
                                "strategy": strategy.name,
                                "volatility": (
                                    float(context.get_market_volatility())
                                    if context
                                    else None
                                ),
                            },
                        )

                    import asyncio

                    asyncio.get_running_loop().create_task(write())
            except Exception:
                pass

            return result

        except Exception as e:
            self.logger.error(
                f"Failed to calculate position size for {request.symbol}: {e}"
            )

            # Возвращаем результат с ошибкой
            error_result = PositionSizeResult(is_valid=False, errors=[str(e)])

            return SizingResult(
                base_result=error_result,
                sizing_context=context or SizingContext(symbol=request.symbol),
                constraints=constraints or SizingConstraints(),
            )

    def _calculate_base_position_size(
        self,
        request: PositionSizeRequest,
        context: SizingContext,
        strategy: SizingStrategy,
    ) -> PositionSizeResult:
        """Расчет базового размера позиции"""

        # Рассчитываем риск на основе стратегии
        risk_amount = self._calculate_risk_amount(request, context, strategy)

        # Рассчитываем расстояние до стопа
        stop_distance = abs(request.entry_price - request.stop_price)

        # Рассчитываем размер позиции
        position_size = risk_amount / stop_distance

        # Корректируем на размер лота
        position_size = self._adjust_for_lot_size(position_size, request.lot_size)

        # Рассчитываем стоимость позиции
        position_value = position_size * request.entry_price

        # Рассчитываем плечо
        leverage_used = position_value / request.balance

        # Рассчитываем требуемую маржу
        margin_required = position_value / leverage_used

        # Рассчитываем расстояние до ликвидации
        liquidation_distance = self._calculate_liquidation_distance(
            request.entry_price, request.stop_price, leverage_used
        )

        # Рассчитываем соотношение риск/доходность
        risk_reward_ratio = self._calculate_risk_reward_ratio(
            request.entry_price, request.stop_price
        )

        return PositionSizeResult(
            is_valid=True,
            position_size=position_size,
            position_value=position_value,
            risk_amount=risk_amount,
            leverage_used=leverage_used,
            margin_required=margin_required,
            liquidation_distance=liquidation_distance,
            risk_reward_ratio=risk_reward_ratio,
        )

    def _calculate_risk_amount(
        self,
        request: PositionSizeRequest,
        context: SizingContext,
        strategy: SizingStrategy,
    ) -> Decimal:
        """Расчет суммы риска"""

        # Базовый риск
        base_risk = request.balance * request.risk_per_trade

        # Корректировка на основе стратегии
        if strategy.risk_method == "volatility_adjusted":
            volatility = context.get_market_volatility()
            risk_multiplier = strategy.get_risk_multiplier(volatility)
            base_risk = request.balance * Decimal(str(risk_multiplier))

        # Корректировка на основе толерантности к риску
        risk_tolerance = context.get_user_risk_tolerance()
        if risk_tolerance == "low":
            base_risk *= Decimal("0.5")
        elif risk_tolerance == "high":
            base_risk *= Decimal("1.5")

        # Ограничиваем максимальным риском
        max_risk = request.balance * Decimal(str(self.config.max_risk_per_trade))
        return min(base_risk, max_risk)

    def _adjust_for_lot_size(
        self, position_size: Decimal, lot_size: Decimal
    ) -> Decimal:
        """Корректировка размера позиции под размер лота"""
        if lot_size <= 0:
            return position_size

        # Округляем вниз до ближайшего лота
        return (position_size // lot_size) * lot_size

    def _calculate_liquidation_distance(
        self, entry_price: Decimal, stop_price: Decimal, leverage: Decimal
    ) -> Decimal:
        """Расчет расстояния до ликвидации"""
        # Упрощенный расчет - в реальности нужно учитывать MMR и комиссии
        liquidation_price = entry_price * (1 - Decimal("1") / leverage)
        return abs(entry_price - liquidation_price) / entry_price

    def _calculate_risk_reward_ratio(
        self, entry_price: Decimal, stop_price: Decimal
    ) -> Decimal:
        """Расчет соотношения риск/доходность"""
        # Упрощенный расчет - предполагаем тейк-профит в 2 раза дальше стопа
        stop_distance = abs(entry_price - stop_price)
        take_distance = stop_distance * Decimal("2")  # 1:2 соотношение

        return take_distance / stop_distance

    def _create_constraints(self, request: PositionSizeRequest) -> SizingConstraints:
        """Создание ограничений для расчета"""
        return SizingConstraints(
            max_position_size_usdt=Decimal(str(self.config.max_position_size_usdt)),
            max_leverage=Decimal(str(self.config.max_leverage)),
            min_position_size_usdt=Decimal("10.0"),
            max_risk_per_trade=Decimal(str(self.config.max_risk_per_trade)),
            max_portfolio_risk=Decimal("0.20"),
            correlation_limit=Decimal("0.7"),
        )

    def _create_default_strategy(self) -> SizingStrategy:
        """Создание стратегии по умолчанию"""
        return SizingStrategy(
            name="default",
            risk_method="percentage",
            position_sizing_method="equal_weight",
            rebalancing_frequency="daily",
            parameters={
                "base_risk": self.config.default_risk_per_trade,
                "fixed_risk": self.config.default_risk_per_trade,
            },
        )

    def _apply_constraints_and_adjustments(
        self,
        base_result: PositionSizeResult,
        request: PositionSizeRequest,
        context: SizingContext,
        constraints: SizingConstraints,
        strategy: SizingStrategy,
    ) -> PositionSizeResult:
        """Применение ограничений и корректировок"""

        result = base_result
        adjustments = []

        # Проверяем максимальный размер позиции
        if result.position_value > constraints.max_position_size_usdt:
            # Уменьшаем размер позиции
            scale_factor = constraints.max_position_size_usdt / result.position_value
            result.position_size *= scale_factor
            result.position_value *= scale_factor
            result.risk_amount *= scale_factor
            result.margin_required *= scale_factor
            adjustments.append(f"Scaled down to max position size: {scale_factor:.3f}")

        # Проверяем максимальное плечо
        if result.leverage_used > constraints.max_leverage:
            # Уменьшаем плечо
            scale_factor = constraints.max_leverage / result.leverage_used
            result.position_size *= scale_factor
            result.position_value *= scale_factor
            result.leverage_used = constraints.max_leverage
            result.margin_required = result.position_value / result.leverage_used
            adjustments.append(f"Scaled down to max leverage: {scale_factor:.3f}")

        # Проверяем минимальный размер позиции
        if result.position_value < constraints.min_position_size_usdt:
            result.add_error(
                f"Position value {result.position_value} below minimum {constraints.min_position_size_usdt}"
            )

        # Проверяем максимальный риск
        if result.risk_amount > request.balance * constraints.max_risk_per_trade:
            result.add_error(
                f"Risk amount {result.risk_amount} exceeds maximum {request.balance * constraints.max_risk_per_trade}"
            )

        # Проверяем соотношение риск/доходность
        if result.risk_reward_ratio < self.min_risk_reward_ratio:
            result.add_warning(
                f"Risk/reward ratio {result.risk_reward_ratio} below minimum {self.min_risk_reward_ratio}"
            )

        # Добавляем информацию об корректировках
        if adjustments:
            result.warnings.extend(adjustments)

        return result

    def _calculate_risk_metrics(
        self, result: PositionSizeResult, context: SizingContext
    ) -> dict[str, Any]:
        """Расчет метрик риска"""

        volatility = context.get_market_volatility()
        correlation_risk = context.get_correlation_risk()

        return {
            "volatility_risk": float(volatility),
            "correlation_risk": float(correlation_risk),
            "liquidation_risk": float(result.liquidation_distance),
            "leverage_risk": float(result.leverage_used),
            "concentration_risk": (
                float(result.position_value / result.risk_amount)
                if result.risk_amount > 0
                else 0.0
            ),
            "overall_risk_score": self._calculate_overall_risk_score(result, context),
        }

    def _calculate_overall_risk_score(
        self, result: PositionSizeResult, context: SizingContext
    ) -> float:
        """Расчет общего скора риска (0-1, где 1 - максимальный риск)"""

        # Факторы риска
        leverage_factor = min(
            1.0, float(result.leverage_used) / 20.0
        )  # Нормализуем к 20x
        volatility_factor = context.get_market_volatility() * 10  # Нормализуем к 10%
        correlation_factor = context.get_correlation_risk()
        liquidation_factor = min(
            1.0, float(result.liquidation_distance) * 10
        )  # Нормализуем к 10%

        # Взвешенная сумма
        overall_score = (
            leverage_factor * 0.3
            + volatility_factor * 0.25
            + correlation_factor * 0.25
            + liquidation_factor * 0.2
        )

        return min(1.0, overall_score)

    def _calculate_portfolio_impact(
        self, result: PositionSizeResult, context: SizingContext
    ) -> dict[str, Any]:
        """Расчет влияния на портфель"""

        current_portfolio_value = context.current_portfolio.get(
            "total_value", Decimal("10000.0")
        )
        current_positions_count = context.current_portfolio.get("positions_count", 0)

        # Вклад в общий риск портфеля
        portfolio_risk_contribution = result.risk_amount / current_portfolio_value

        # Вклад в общую стоимость портфеля
        portfolio_value_contribution = result.position_value / current_portfolio_value

        # Влияние на диверсификацию
        diversification_impact = 1.0 / (
            current_positions_count + 1
        )  # Чем больше позиций, тем лучше диверсификация

        return {
            "risk_contribution": portfolio_risk_contribution,
            "value_contribution": portfolio_value_contribution,
            "diversification_impact": diversification_impact,
            "new_positions_count": current_positions_count + 1,
            "portfolio_concentration": portfolio_value_contribution,
        }
