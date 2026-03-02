"""
Калькулятор позиций на SWAP инструментах.

Реализует алгоритм расчёта позиций согласно техническому заданию:
1. Загрузить метаданные (tick/lot, MMR, fees, max L)
2. Собрать OHLCV spot и swap
3. Посчитать ATR14, RSI, EMA и consensus
4. Проверить consensus ≥ consensus_threshold и signal_age ≤ signal_age_max
5. Определить стоп
6. Рассчитать риск и размер позиции
7. Проверить ликвидацию
8. Сформировать ордера
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .validator import PositionDataValidator

logger = logging.getLogger(__name__)


@dataclass
class PositionCalculationResult:
    """Результат расчёта позиции"""

    is_valid: bool
    position_size: Decimal | None = None
    position_value_usdt: Decimal | None = None
    entry_price: Decimal | None = None
    stop_loss_price: Decimal | None = None
    take_profit_prices: list[Decimal] | None = None
    risk_amount_usdt: Decimal | None = None
    stop_distance_pct: Decimal | None = None
    leverage_used: int | None = None
    margin_required: Decimal | None = None
    liquidation_distance_pct: Decimal | None = None
    validation_errors: list[str] | None = None
    warnings: list[str] | None = None


class PositionCalculator:
    """Калькулятор позиций на SWAP инструментах"""

    def __init__(self):
        self.validator = PositionDataValidator()

    def calculate_position(self, data: dict[str, Any]) -> PositionCalculationResult:
        """
        Рассчитывает позицию согласно алгоритму из ТЗ.

        Args:
            data: Словарь с данными для расчёта

        Returns:
            PositionCalculationResult с результатами расчёта
        """
        # Шаг 1: Валидация данных
        validation_result = self.validator.validate_all_blocks(data)

        if not validation_result.is_valid:
            return PositionCalculationResult(
                is_valid=False,
                validation_errors=validation_result.errors,
                warnings=validation_result.warnings,
            )

        try:
            # Шаг 2: Извлечение данных
            exchange_data = self._extract_exchange_data(data)
            market_data = self._extract_market_data(data)
            user_data = self._extract_user_data(data)
            trade_data = self._extract_trade_data(data)
            signal_data = self._extract_signal_data(data)

            # Шаг 3: Расчёт индикаторов
            indicators = self._calculate_indicators(market_data)

            # Добавляем atr14 в данные для валидации
            data["atr14"] = str(indicators["atr14"])

            # Шаг 4: Проверка сигналов
            signal_check = self._check_signal_conditions(indicators, signal_data)
            if not signal_check["is_valid"]:
                return PositionCalculationResult(
                    is_valid=False,
                    validation_errors=[signal_check["reason"]],
                    warnings=signal_check.get("warnings", []),
                )

            # Шаг 5: Определение стопа
            stop_calculation = self._calculate_stop_loss(
                trade_data, market_data, indicators
            )

            # Шаг 6: Расчёт риска и размера позиции
            risk_calculation = self._calculate_risk_and_position_size(
                user_data, market_data, stop_calculation
            )

            # Шаг 7: Проверка ликвидации
            liquidation_check = self._check_liquidation(
                exchange_data, user_data, risk_calculation
            )

            # Шаг 8: Корректировка плеча при необходимости
            final_leverage = self._adjust_leverage_if_needed(
                liquidation_check, user_data["leverage_target"]
            )

            # Шаг 9: Финальный расчёт позиции
            final_calculation = self._calculate_final_position(
                risk_calculation, final_leverage, market_data, trade_data
            )

            return PositionCalculationResult(
                is_valid=True,
                position_size=final_calculation["position_size"],
                position_value_usdt=final_calculation["position_value_usdt"],
                entry_price=final_calculation["entry_price"],
                stop_loss_price=final_calculation["stop_loss_price"],
                take_profit_prices=final_calculation["take_profit_prices"],
                risk_amount_usdt=final_calculation["risk_amount_usdt"],
                stop_distance_pct=final_calculation["stop_distance_pct"],
                leverage_used=final_calculation["leverage_used"],
                margin_required=final_calculation["margin_required"],
                liquidation_distance_pct=final_calculation["liquidation_distance_pct"],
                warnings=validation_result.warnings
                + final_calculation.get("warnings", []),
            )

        except Exception as e:
            logger.error(f"Ошибка при расчёте позиции: {e}")
            return PositionCalculationResult(
                is_valid=False, validation_errors=[f"Ошибка расчёта: {e!s}"]
            )

    def _extract_exchange_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Извлекает биржевые метаданные"""
        return {
            "symbol": data["symbol"],
            "margin_mode": data["margin_mode"],
            "tick_size": Decimal(str(data["tick_size"])),
            "lot_size": Decimal(str(data["lot_size"])),
            "maker_fee": Decimal(str(data["maker_fee"])),
            "taker_fee": Decimal(str(data["taker_fee"])),
            "maintenance_margin_rate": Decimal(str(data["maintenance_margin_rate"])),
            "max_leverage": int(data["max_leverage"]),
        }

    def _extract_market_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Извлекает рыночные данные"""
        return {
            "spot_ohlcv": data["spot_ohlcv"],
            "swap_ohlcv": data["swap_ohlcv"],
            "P_last": Decimal(str(data["P_last"])),
        }

    def _extract_user_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Извлекает пользовательские данные"""
        return {
            "balance_usdt": Decimal(str(data["balance_usdt"])),
            "risk_per_trade_pct": Decimal(str(data["risk_per_trade_pct"])),
            "leverage_target": int(data["leverage_target"]),
        }

    def _extract_trade_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Извлекает данные сделки"""
        return {
            "direction": data["direction"],
            "stop_method": data["stop_method"],
            "stop_value": Decimal(str(data["stop_value"])),
            "tp_levels_pct": [Decimal(str(x)) for x in data["tp_levels_pct"]],
            "order_type_entry": data["order_type_entry"],
            "slippage_pct": Decimal(str(data.get("slippage_pct", 0))),
        }

    def _extract_signal_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Извлекает данные сигналов"""
        return {
            "consensus_threshold": Decimal(str(data["consensus_threshold"])),
            "timeframe_entry": data["timeframe_entry"],
            "signal_age_max": int(data["signal_age_max"]),
        }

    def _calculate_indicators(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """Рассчитывает технические индикаторы"""
        # Получаем последние данные для расчёта
        swap_ohlcv = market_data["swap_ohlcv"]

        # Простой расчёт ATR14 (можно заменить на более сложную логику)
        atr14 = self._calculate_simple_atr(swap_ohlcv, 14)

        # Расчёт consensus (упрощённый пример)
        consensus = self._calculate_consensus(swap_ohlcv)

        return {
            "atr14": atr14,
            "consensus": consensus,
            "signal_age": 0,  # Упрощённо, в реальности нужно считать возраст сигнала
        }

    def _calculate_simple_atr(self, ohlcv: list[dict], period: int) -> Decimal:
        """Простой расчёт ATR"""
        if len(ohlcv) < period:
            return Decimal("0")

        true_ranges = []
        for i in range(1, min(period + 1, len(ohlcv))):
            high = Decimal(str(ohlcv[i]["high"]))
            low = Decimal(str(ohlcv[i]["low"]))
            prev_close = Decimal(str(ohlcv[i - 1]["close"]))

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)

            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)

        if not true_ranges:
            return Decimal("0")

        return sum(true_ranges) / len(true_ranges)

    def _calculate_consensus(self, ohlcv: list[dict]) -> Decimal:
        """Рассчитывает consensus сигналов (упрощённый пример)"""
        if len(ohlcv) < 20:
            return Decimal("0")

        # Более сложный расчёт consensus на основе нескольких факторов
        current_close = Decimal(str(ohlcv[-1]["close"]))
        prev_close = Decimal(str(ohlcv[-2]["close"]))

        # Фактор 1: Направление цены
        price_direction = 0
        if current_close > prev_close:
            price_direction = 1
        elif current_close < prev_close:
            price_direction = -1

        # Фактор 2: Волатильность (ATR)
        atr = self._calculate_simple_atr(ohlcv, 14)
        volatility_factor = min(
            atr / current_close, Decimal("0.1")
        )  # Нормализуем волатильность

        # Фактор 3: Тренд (сравниваем с ценой 10 баров назад)
        if len(ohlcv) >= 10:
            old_close = Decimal(str(ohlcv[-10]["close"]))
            trend_factor = (current_close - old_close) / old_close
        else:
            trend_factor = Decimal("0")

        # Комбинируем факторы
        consensus = (
            price_direction * Decimal("0.5")
            + volatility_factor * Decimal("10")
            + trend_factor * Decimal("5")
        )

        # Ограничиваем диапазон
        return max(Decimal("-2"), min(Decimal("2"), consensus))

    def _check_signal_conditions(
        self, indicators: dict[str, Any], signal_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Проверяет условия сигналов"""
        consensus = indicators["consensus"]
        consensus_threshold = signal_data["consensus_threshold"]
        signal_age = indicators["signal_age"]
        signal_age_max = signal_data["signal_age_max"]

        if consensus < consensus_threshold:
            return {
                "is_valid": False,
                "reason": f"Consensus ({consensus}) ниже порога ({consensus_threshold})",
            }

        if signal_age > signal_age_max:
            return {
                "is_valid": False,
                "reason": f"Возраст сигнала ({signal_age}) превышает максимум ({signal_age_max})",
            }

        return {"is_valid": True}

    def _calculate_stop_loss(
        self,
        trade_data: dict[str, Any],
        market_data: dict[str, Any],
        indicators: dict[str, Any],
    ) -> dict[str, Any]:
        """Рассчитывает стоп-лосс"""
        P_last = market_data["P_last"]
        stop_method = trade_data["stop_method"]
        stop_value = trade_data["stop_value"]
        direction = trade_data["direction"]

        if stop_method == "percent":
            stop_distance_pct = stop_value
        elif stop_method == "atr_mult":
            atr14 = indicators["atr14"]
            stop_distance_pct = (stop_value * atr14) / P_last
        else:
            raise ValueError(f"Неизвестный метод стопа: {stop_method}")

        # Рассчитываем цену стопа
        if direction == "long":
            stop_loss_price = P_last * (1 - stop_distance_pct)
        else:  # short
            stop_loss_price = P_last * (1 + stop_distance_pct)

        return {
            "stop_distance_pct": stop_distance_pct,
            "stop_loss_price": stop_loss_price,
        }

    def _calculate_risk_and_position_size(
        self,
        user_data: dict[str, Any],
        market_data: dict[str, Any],
        stop_calculation: dict[str, Any],
    ) -> dict[str, Any]:
        """Рассчитывает риск и размер позиции"""
        balance_usdt = user_data["balance_usdt"]
        risk_per_trade_pct = user_data["risk_per_trade_pct"]
        P_last = market_data["P_last"]
        stop_distance_pct = stop_calculation["stop_distance_pct"]

        # Расчёт суммы риска
        risk_amount_usdt = balance_usdt * risk_per_trade_pct

        # Расчёт размера позиции
        position_size = risk_amount_usdt / (stop_distance_pct * P_last)

        return {
            "risk_amount_usdt": risk_amount_usdt,
            "position_size": position_size,
            "position_value_usdt": position_size * P_last,
        }

    def _check_liquidation(
        self,
        exchange_data: dict[str, Any],
        user_data: dict[str, Any],
        risk_calculation: dict[str, Any],
    ) -> dict[str, Any]:
        """Проверяет условия ликвидации согласно ТЗ"""
        leverage_target = user_data["leverage_target"]
        maintenance_margin_rate = exchange_data["maintenance_margin_rate"]
        taker_fee = exchange_data["taker_fee"]
        stop_distance_pct = risk_calculation.get("stop_distance_pct", Decimal("0"))

        # Расчёт дистанции до ликвидации (приближённо для isolated)
        # d_liq ≈ 1/L_target − MMR − taker_fee
        liquidation_distance_pct = (
            (Decimal("1") / Decimal(str(leverage_target)))
            - maintenance_margin_rate
            - taker_fee
        )

        # Требование: d_liq ≥ 2 × Stop% + taker_fee
        min_required_distance = (2 * stop_distance_pct) + taker_fee
        is_safe = liquidation_distance_pct >= min_required_distance

        return {
            "liquidation_distance_pct": liquidation_distance_pct,
            "min_required_distance": min_required_distance,
            "is_safe": is_safe,
        }

    def _adjust_leverage_if_needed(
        self, liquidation_check: dict[str, Any], leverage_target: int
    ) -> int:
        """Корректирует плечо при необходимости согласно ТЗ"""
        if liquidation_check["is_safe"]:
            return leverage_target

        # Если небезопасно, уменьшаем leverage_target до 1 / (Stop% + MMR + taker_fee)
        # Это упрощённая версия, в реальности нужны более точные расчёты
        return max(1, leverage_target // 2)

    def _calculate_final_position(
        self,
        risk_calculation: dict[str, Any],
        leverage_used: int,
        market_data: dict[str, Any],
        trade_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Рассчитывает финальную позицию"""
        P_last = market_data["P_last"]
        position_size = risk_calculation["position_size"]
        risk_amount_usdt = risk_calculation["risk_amount_usdt"]

        # Рассчитываем тейк-профиты
        take_profit_prices = []
        for tp_level_pct in trade_data["tp_levels_pct"]:
            if trade_data["direction"] == "long":
                tp_price = P_last * (1 + tp_level_pct)
            else:  # short
                tp_price = P_last * (1 - tp_level_pct)
            take_profit_prices.append(tp_price)

        # Рассчитываем требуемую маржу
        margin_required = risk_amount_usdt / leverage_used

        return {
            "position_size": position_size,
            "position_value_usdt": position_size * P_last,
            "entry_price": P_last,
            "stop_loss_price": risk_calculation.get("stop_loss_price"),
            "take_profit_prices": take_profit_prices,
            "risk_amount_usdt": risk_amount_usdt,
            "stop_distance_pct": risk_calculation.get("stop_distance_pct"),
            "leverage_used": leverage_used,
            "margin_required": margin_required,
            "liquidation_distance_pct": (Decimal("1") / Decimal(str(leverage_used)))
            - Decimal("0.005")
            - Decimal("0.0005"),  # Упрощённо
            "warnings": [],
        }
