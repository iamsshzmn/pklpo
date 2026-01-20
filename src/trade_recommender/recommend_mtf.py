"""
Расширенный Trade Recommender с интеграцией MTF данных

Дополняет существующий Trade Recommender MTF сигналами для повышения точности рекомендаций.
"""

import logging
from typing import Any

from ..mtf.integrator import MTFSignalData, mtf_integrator
from .recommend import recommend_for_score

logger = logging.getLogger(__name__)


class MTFEnhancedTradeRecommender:
    """Расширенный Trade Recommender с MTF интеграцией"""

    def __init__(self, mtf_weight: float = 0.3):
        self.mtf_weight = mtf_weight
        self.logger = logging.getLogger(__name__)

    async def recommend_for_score_with_mtf(
        self, score_id: int, dry_run: bool = True, use_mtf: bool = True
    ) -> dict[str, Any]:
        """
        Генерирует торговую рекомендацию с учётом MTF данных

        Args:
            score_id: ID score_result
            dry_run: Режим тестирования
            use_mtf: Использовать ли MTF данные

        Returns:
            Словарь с результатом рекомендации
        """
        # Базовая рекомендация
        base_recommendation = await recommend_for_score(score_id, dry_run)

        if not use_mtf or base_recommendation.get("status") != "ready":
            return base_recommendation

        try:
            # Получаем информацию о символе
            symbol = base_recommendation.get("symbol")
            if not symbol:
                self.logger.warning(
                    "Символ не найден в рекомендации, MTF интеграция пропущена"
                )
                return base_recommendation

            # Получаем MTF сигнал
            mtf_data = await mtf_integrator.get_latest_mtf_signal(symbol)
            if not mtf_data:
                self.logger.info(
                    f"MTF сигнал не найден для {symbol}, используем базовую рекомендацию"
                )
                return base_recommendation

            # Анализируем MTF сигнал
            mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)
            mtf_strength = mtf_integrator.get_mtf_strength(mtf_data)

            self.logger.info(f"MTF анализ для рекомендации {symbol}:")
            self.logger.info(f"  Направление: {mtf_direction}")
            self.logger.info(f"  Уверенность: {mtf_confidence:.3f}")
            self.logger.info(f"  Сила: {mtf_strength}")

            # Применяем MTF корректировки
            enhanced_recommendation = self._apply_mtf_corrections(
                base_recommendation, mtf_data
            )

            # Добавляем MTF информацию
            enhanced_recommendation["mtf_data"] = {
                "direction": mtf_direction,
                "confidence": mtf_confidence,
                "strength": mtf_strength,
                "context_score": mtf_data.context_score,
                "bias": mtf_data.bias,
                "p_reversal_up": mtf_data.p_reversal_up,
                "p_reversal_down": mtf_data.p_reversal_down,
            }

            return enhanced_recommendation

        except Exception as e:
            self.logger.error(
                f"Ошибка при MTF интеграции для рекомендации {score_id}: {e}"
            )
            return base_recommendation

    def _apply_mtf_corrections(
        self, base_recommendation: dict[str, Any], mtf_data: MTFSignalData
    ) -> dict[str, Any]:
        """
        Применяет MTF корректировки к базовой рекомендации

        Args:
            base_recommendation: Базовая рекомендация
            mtf_data: MTF данные

        Returns:
            Скорректированная рекомендация
        """
        enhanced_recommendation = base_recommendation.copy()

        # Корректируем направление на основе MTF consensus
        base_direction = base_recommendation.get("direction")
        mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)

        if base_direction and mtf_direction != "FLAT":
            # Если MTF сигнал сильный, корректируем направление
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            if mtf_confidence > 0.6:  # Сильный MTF сигнал
                if base_direction != mtf_direction:
                    self.logger.info(
                        f"MTF корректировка направления: {base_direction} -> {mtf_direction}"
                    )
                    enhanced_recommendation["direction"] = mtf_direction
                    enhanced_recommendation["mtf_direction_override"] = True

        # Корректируем размер позиции на основе MTF уверенности
        if base_recommendation.get("position_size") and mtf_data.consensus != 0:
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # Увеличиваем размер позиции при высокой MTF уверенности
            confidence_multiplier = 1.0 + (mtf_confidence - 0.5) * self.mtf_weight

            base_size = float(base_recommendation["position_size"])
            enhanced_size = base_size * confidence_multiplier

            enhanced_recommendation["position_size"] = enhanced_size
            enhanced_recommendation["position_value_usdt"] = enhanced_size * float(
                base_recommendation.get("entry_price", 0)
            )

            self.logger.info(
                f"MTF корректировка размера позиции: {base_size:.6f} -> {enhanced_size:.6f}"
            )

        # Корректируем стоп-лосс на основе MTF context_score
        if (
            base_recommendation.get("stop_loss_price")
            and mtf_data.context_score is not None
        ):
            base_stop = float(base_recommendation["stop_loss_price"])
            base_entry = float(base_recommendation.get("entry_price", 0))

            if base_entry > 0:
                # При сильном тренде увеличиваем расстояние стопа
                context_multiplier = (
                    1.0 + abs(mtf_data.context_score) * self.mtf_weight * 0.5
                )

                if mtf_data.consensus == 1:  # LONG
                    # Увеличиваем расстояние до стопа
                    stop_distance = base_entry - base_stop
                    new_stop_distance = stop_distance * context_multiplier
                    enhanced_stop = base_entry - new_stop_distance
                elif mtf_data.consensus == -1:  # SHORT
                    # Увеличиваем расстояние до стопа
                    stop_distance = base_stop - base_entry
                    new_stop_distance = stop_distance * context_multiplier
                    enhanced_stop = base_entry + new_stop_distance
                else:
                    enhanced_stop = base_stop

                enhanced_recommendation["stop_loss_price"] = enhanced_stop
                self.logger.info(
                    f"MTF корректировка стопа: {base_stop:.6f} -> {enhanced_stop:.6f}"
                )

        # Корректируем take-profit на основе MTF вероятностей разворота
        if base_recommendation.get("take_profit_price") and mtf_data.consensus != 0:
            base_tp = float(base_recommendation["take_profit_price"])
            base_entry = float(base_recommendation.get("entry_price", 0))

            if base_entry > 0:
                if mtf_data.consensus == 1:  # LONG
                    # Увеличиваем take-profit при высокой вероятности разворота вверх
                    tp_multiplier = 1.0 + mtf_data.p_reversal_up * self.mtf_weight
                else:  # SHORT
                    # Увеличиваем take-profit при высокой вероятности разворота вниз
                    tp_multiplier = 1.0 + mtf_data.p_reversal_down * self.mtf_weight

                if mtf_data.consensus == 1:  # LONG
                    tp_distance = base_tp - base_entry
                    new_tp_distance = tp_distance * tp_multiplier
                    enhanced_tp = base_entry + new_tp_distance
                else:  # SHORT
                    tp_distance = base_entry - base_tp
                    new_tp_distance = tp_distance * tp_multiplier
                    enhanced_tp = base_entry - new_tp_distance

                enhanced_recommendation["take_profit_price"] = enhanced_tp
                self.logger.info(
                    f"MTF корректировка take-profit: {base_tp:.6f} -> {enhanced_tp:.6f}"
                )

        return enhanced_recommendation

    async def validate_mtf_recommendation(
        self, symbol: str, recommendation: dict[str, Any], min_confidence: float = 0.4
    ) -> dict[str, Any]:
        """
        Проверяет соответствие рекомендации MTF сигналу

        Args:
            symbol: Торговый символ
            recommendation: Рекомендация
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
                    "recommendation_direction": "UNKNOWN",
                }

            recommendation_direction = recommendation.get("direction", "UNKNOWN")
            mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # Проверяем соответствие направления
            is_aligned = (
                recommendation_direction == "LONG" and mtf_direction == "LONG"
            ) or (recommendation_direction == "SHORT" and mtf_direction == "SHORT")

            # Проверяем уверенность
            is_confident = mtf_confidence >= min_confidence

            return {
                "is_aligned": is_aligned and is_confident,
                "reason": f"Recommendation: {recommendation_direction}, MTF: {mtf_direction} (confidence: {mtf_confidence:.3f})",
                "recommendation_direction": recommendation_direction,
                "mtf_direction": mtf_direction,
                "mtf_confidence": mtf_confidence,
                "mtf_strength": mtf_integrator.get_mtf_strength(mtf_data),
                "context_score": mtf_data.context_score,
                "bias": mtf_data.bias,
            }

        except Exception as e:
            self.logger.error(
                f"Ошибка при MTF валидации рекомендации для {symbol}: {e}"
            )
            return {
                "is_aligned": False,
                "reason": f"Ошибка MTF валидации: {e}",
                "recommendation_direction": "ERROR",
                "mtf_direction": "ERROR",
            }

    async def get_mtf_enhanced_recommendations(
        self, score_ids: list[int], dry_run: bool = True, use_mtf: bool = True
    ) -> dict[str, Any]:
        """
        Получает MTF-улучшенные рекомендации для списка score_ids

        Args:
            score_ids: Список ID score_results
            dry_run: Режим тестирования
            use_mtf: Использовать ли MTF данные

        Returns:
            Словарь с результатами обработки
        """
        results = {
            "total": len(score_ids),
            "processed": 0,
            "ready": 0,
            "rejected": 0,
            "errors": 0,
            "mtf_aligned": 0,
            "details": [],
        }

        self.logger.info(
            f"Начинаем обработку {len(score_ids)} score_results с MTF интеграцией"
        )

        for i, score_id in enumerate(score_ids, 1):
            try:
                self.logger.info(
                    f"[{i}/{len(score_ids)}] Обработка score_id={score_id}"
                )

                # Генерируем MTF-улучшенную рекомендацию
                recommendation = await self.recommend_for_score_with_mtf(
                    score_id, dry_run=dry_run, use_mtf=use_mtf
                )

                # Анализируем результат
                status = recommendation.get("status", "unknown")
                results["processed"] += 1

                if status == "ready":
                    results["ready"] += 1

                    # Проверяем MTF выравнивание
                    symbol = recommendation.get("symbol")
                    if symbol:
                        mtf_validation = await self.validate_mtf_recommendation(
                            symbol, recommendation
                        )
                        if mtf_validation.get("is_aligned"):
                            results["mtf_aligned"] += 1
                            self.logger.info(
                                f"✅ score_id={score_id}: MTF-выровненная рекомендация готова"
                            )
                        else:
                            self.logger.info(
                                f"⚠️ score_id={score_id}: Рекомендация готова, но не выровнена с MTF"
                            )
                    else:
                        self.logger.info(f"✅ score_id={score_id}: Рекомендация готова")

                elif status == "rejected":
                    results["rejected"] += 1
                    reason = recommendation.get("message", "Неизвестная причина")
                    self.logger.info(f"❌ score_id={score_id}: Отклонено - {reason}")
                elif status == "error":
                    results["errors"] += 1
                    error_msg = recommendation.get("message", "Неизвестная ошибка")
                    self.logger.error(f"💥 score_id={score_id}: Ошибка - {error_msg}")
                else:
                    results["errors"] += 1
                    self.logger.warning(
                        f"⚠️ score_id={score_id}: Неизвестный статус - {status}"
                    )

                # Сохраняем детали
                results["details"].append(
                    {
                        "score_id": score_id,
                        "status": status,
                        "symbol": recommendation.get("symbol"),
                        "direction": recommendation.get("direction"),
                        "mtf_data": recommendation.get("mtf_data"),
                        "message": recommendation.get("message"),
                    }
                )

            except Exception as e:
                results["errors"] += 1
                self.logger.error(
                    f"💥 Критическая ошибка при обработке score_id={score_id}: {e}"
                )
                results["details"].append(
                    {"score_id": score_id, "status": "error", "message": str(e)}
                )

        # Выводим итоговую статистику
        self.logger.info("📊 ИТОГОВАЯ СТАТИСТИКА MTF-РЕКОМЕНДАЦИЙ:")
        self.logger.info(f"📋 Всего записей: {results['total']}")
        self.logger.info(f"✅ Обработано: {results['processed']}")
        self.logger.info(f"🎯 Готовых рекомендаций: {results['ready']}")
        self.logger.info(f"🧭 MTF-выровненных: {results['mtf_aligned']}")
        self.logger.info(f"❌ Отклонённых: {results['rejected']}")
        self.logger.info(f"💥 Ошибок: {results['errors']}")

        if results["ready"] > 0:
            mtf_alignment_rate = results["mtf_aligned"] / results["ready"] * 100
            self.logger.info(f"📈 MTF выравнивание: {mtf_alignment_rate:.1f}%")

        return results


# Глобальный экземпляр MTF-улучшенного trade recommender
mtf_trade_recommender = MTFEnhancedTradeRecommender()
