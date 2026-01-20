"""
Расширенный калькулятор позиций с интеграцией MTF данных

Дополняет существующий PositionCalculator MTF сигналами для повышения точности.
"""

import logging
from decimal import Decimal
from typing import Any

from ..mtf.integrator import MTFSignalData, mtf_integrator
from .calculator import PositionCalculationResult, PositionCalculator

logger = logging.getLogger(__name__)


class MTFEnhancedPositionCalculator(PositionCalculator):
    """Расширенный калькулятор позиций с MTF интеграцией"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

    async def calculate_position_with_mtf(
        self, data: dict[str, Any], use_mtf: bool = True, mtf_weight: float = 0.3
    ) -> PositionCalculationResult:
        """
        Рассчитывает позицию с учётом MTF данных

        Args:
            data: Входные данные для расчёта позиции
            use_mtf: Использовать ли MTF данные
            mtf_weight: Вес MTF сигнала (0.0 - 1.0)

        Returns:
            PositionCalculationResult с MTF корректировками
        """
        # Базовый расчёт позиции
        base_result = self.calculate_position(data)

        if not use_mtf or not base_result.is_valid:
            return base_result

        try:
            # Получаем MTF сигнал
            symbol = data.get("symbol")
            if not symbol:
                self.logger.warning("Символ не указан, MTF интеграция пропущена")
                return base_result

            mtf_data = await mtf_integrator.get_latest_mtf_signal(symbol)
            if not mtf_data:
                self.logger.info(
                    f"MTF сигнал не найден для {symbol}, используем базовый расчёт"
                )
                return base_result

            # Анализируем MTF сигнал
            mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)
            mtf_strength = mtf_integrator.get_mtf_strength(mtf_data)
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            self.logger.info(f"MTF анализ для {symbol}:")
            self.logger.info(f"  Направление: {mtf_direction}")
            self.logger.info(f"  Сила: {mtf_strength}")
            self.logger.info(f"  Уверенность: {mtf_confidence:.3f}")
            self.logger.info(f"  Context Score: {mtf_data.context_score:.3f}")
            self.logger.info(f"  Bias: {mtf_data.bias}")

            # Применяем MTF корректировки
            enhanced_result = self._apply_mtf_corrections(
                base_result, mtf_data, mtf_weight
            )

            # Добавляем MTF информацию в warnings
            mtf_warnings = [
                f"MTF Direction: {mtf_direction}",
                f"MTF Strength: {mtf_strength}",
                f"MTF Confidence: {mtf_confidence:.3f}",
                f"MTF Context Score: {mtf_data.context_score:.3f}",
                f"MTF Bias: {mtf_data.bias}",
                f"MTF P(Up): {mtf_data.p_reversal_up:.3f}",
                f"MTF P(Down): {mtf_data.p_reversal_down:.3f}",
            ]

            if enhanced_result.warnings:
                enhanced_result.warnings.extend(mtf_warnings)
            else:
                enhanced_result.warnings = mtf_warnings

            return enhanced_result

        except Exception as e:
            self.logger.error(f"Ошибка при MTF интеграции для {symbol}: {e}")
            return base_result

    def _apply_mtf_corrections(
        self,
        base_result: PositionCalculationResult,
        mtf_data: MTFSignalData,
        mtf_weight: float,
    ) -> PositionCalculationResult:
        """
        Применяет MTF корректировки к базовому результату

        Args:
            base_result: Базовый результат расчёта
            mtf_data: MTF данные
            mtf_weight: Вес MTF корректировки

        Returns:
            Скорректированный результат
        """
        # Создаём копию результата
        enhanced_result = PositionCalculationResult(
            is_valid=base_result.is_valid,
            position_size=base_result.position_size,
            position_value_usdt=base_result.position_value_usdt,
            entry_price=base_result.entry_price,
            stop_loss_price=base_result.stop_loss_price,
            take_profit_prices=base_result.take_profit_prices,
            risk_amount_usdt=base_result.risk_amount_usdt,
            stop_distance_pct=base_result.stop_distance_pct,
            leverage_used=base_result.leverage_used,
            margin_required=base_result.margin_required,
            liquidation_distance_pct=base_result.liquidation_distance_pct,
            validation_errors=base_result.validation_errors,
            warnings=base_result.warnings,
        )

        # Корректируем размер позиции на основе MTF уверенности
        if mtf_data.consensus != 0 and base_result.position_size:
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # Увеличиваем размер позиции при высокой MTF уверенности
            confidence_multiplier = 1.0 + (mtf_confidence - 0.5) * mtf_weight

            enhanced_result.position_size = base_result.position_size * Decimal(
                str(confidence_multiplier)
            )
            enhanced_result.position_value_usdt = (
                base_result.position_value_usdt * Decimal(str(confidence_multiplier))
            )

            self.logger.info(
                f"MTF корректировка размера позиции: {confidence_multiplier:.3f}"
            )

        # Корректируем стоп-лосс на основе MTF context_score
        if mtf_data.context_score is not None and base_result.stop_loss_price:
            # При сильном тренде (высокий context_score) увеличиваем расстояние стопа
            context_multiplier = 1.0 + abs(mtf_data.context_score) * mtf_weight * 0.5

            if mtf_data.consensus == 1:  # LONG
                # Увеличиваем расстояние до стопа
                price_diff = base_result.entry_price - base_result.stop_loss_price
                new_stop_distance = price_diff * Decimal(str(context_multiplier))
                enhanced_result.stop_loss_price = (
                    base_result.entry_price - new_stop_distance
                )
            elif mtf_data.consensus == -1:  # SHORT
                # Увеличиваем расстояние до стопа
                price_diff = base_result.stop_loss_price - base_result.entry_price
                new_stop_distance = price_diff * Decimal(str(context_multiplier))
                enhanced_result.stop_loss_price = (
                    base_result.entry_price + new_stop_distance
                )

            self.logger.info(f"MTF корректировка стопа: {context_multiplier:.3f}")

        # Корректируем take-profit на основе MTF вероятностей разворота
        if mtf_data.consensus != 0 and base_result.take_profit_prices:
            if mtf_data.consensus == 1:  # LONG
                # Увеличиваем take-profit при высокой вероятности разворота вверх
                tp_multiplier = 1.0 + mtf_data.p_reversal_up * mtf_weight
            else:  # SHORT
                # Увеличиваем take-profit при высокой вероятности разворота вниз
                tp_multiplier = 1.0 + mtf_data.p_reversal_down * mtf_weight

            enhanced_result.take_profit_prices = [
                price * Decimal(str(tp_multiplier))
                for price in base_result.take_profit_prices
            ]

            self.logger.info(f"MTF корректировка take-profit: {tp_multiplier:.3f}")

        return enhanced_result

    async def validate_mtf_alignment(
        self, symbol: str, direction: str, min_confidence: float = 0.4
    ) -> dict[str, Any]:
        """
        Проверяет соответствие направления позиции MTF сигналу

        Args:
            symbol: Торговый символ
            direction: Направление позиции ("LONG", "SHORT")
            min_confidence: Минимальная уверенность MTF сигнала

        Returns:
            Словарь с результатами валидации
        """
        try:
            mtf_data = await mtf_integrator.get_latest_mtf_signal(symbol)
            if not mtf_data:
                return {
                    "is_aligned": False,
                    "reason": "MTF сигнал не найден",
                    "mtf_direction": "UNKNOWN",
                    "mtf_confidence": 0.0,
                }

            mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # Проверяем соответствие направления
            is_aligned = (direction == "LONG" and mtf_direction == "LONG") or (
                direction == "SHORT" and mtf_direction == "SHORT"
            )

            # Проверяем уверенность
            is_confident = mtf_confidence >= min_confidence

            return {
                "is_aligned": is_aligned and is_confident,
                "reason": f"MTF: {mtf_direction} (confidence: {mtf_confidence:.3f})",
                "mtf_direction": mtf_direction,
                "mtf_confidence": mtf_confidence,
                "mtf_strength": mtf_integrator.get_mtf_strength(mtf_data),
                "context_score": mtf_data.context_score,
                "bias": mtf_data.bias,
            }

        except Exception as e:
            self.logger.error(f"Ошибка при MTF валидации для {symbol}: {e}")
            return {
                "is_aligned": False,
                "reason": f"Ошибка MTF валидации: {e}",
                "mtf_direction": "ERROR",
                "mtf_confidence": 0.0,
            }
