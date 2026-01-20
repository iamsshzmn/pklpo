"""
Расширенный Scoring Engine с интеграцией MTF данных

Дополняет существующий ScoringEngine MTF сигналами для повышения точности scores.
"""

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from ..database import get_async_session
from ..mtf.integrator import MTFSignalData, mtf_integrator
from .compute import ScoreResult, ScoringEngine

logger = logging.getLogger(__name__)


class MTFEnhancedScoringEngine(ScoringEngine):
    """Расширенный Scoring Engine с MTF интеграцией"""

    def __init__(self, mtf_weight: float = 0.25):
        super().__init__()
        self.mtf_weight = mtf_weight
        self.logger = logging.getLogger(__name__)

    async def compute_score_with_mtf(
        self, symbol: str, timeframe: str, ts: int, use_mtf: bool = True
    ) -> ScoreResult | None:
        """
        Вычисляет score с учётом MTF данных

        Args:
            symbol: Торговый символ
            timeframe: Таймфрейм
            ts: Timestamp
            use_mtf: Использовать ли MTF данные

        Returns:
            ScoreResult с MTF корректировками
        """
        # Базовый расчёт score
        base_result = await self.compute_score(symbol, timeframe, ts)

        if not use_mtf or not base_result:
            return base_result

        try:
            # Получаем MTF сигнал
            mtf_data = await mtf_integrator.get_latest_mtf_signal(symbol)
            if not mtf_data:
                self.logger.info(
                    f"MTF сигнал не найден для {symbol}, используем базовый score"
                )
                return base_result

            # Анализируем MTF сигнал
            mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)
            mtf_strength = mtf_integrator.get_mtf_strength(mtf_data)

            self.logger.info(f"MTF анализ для scoring {symbol}:")
            self.logger.info(f"  Направление: {mtf_direction}")
            self.logger.info(f"  Уверенность: {mtf_confidence:.3f}")
            self.logger.info(f"  Сила: {mtf_strength}")

            # Применяем MTF корректировки
            enhanced_result = self._apply_mtf_corrections(base_result, mtf_data)

            # Добавляем MTF информацию в reasons
            mtf_reasons = [
                f"MTF Direction: {mtf_direction}",
                f"MTF Confidence: {mtf_confidence:.3f}",
                f"MTF Strength: {mtf_strength}",
                f"MTF Context Score: {mtf_data.context_score:.3f}",
                f"MTF Bias: {mtf_data.bias}",
            ]

            if enhanced_result.reasons:
                enhanced_result.reasons.extend(mtf_reasons)
            else:
                enhanced_result.reasons = mtf_reasons

            return enhanced_result

        except Exception as e:
            self.logger.error(f"Ошибка при MTF интеграции для scoring {symbol}: {e}")
            return base_result

    def _apply_mtf_corrections(
        self, base_result: ScoreResult, mtf_data: MTFSignalData
    ) -> ScoreResult:
        """
        Применяет MTF корректировки к базовому score

        Args:
            base_result: Базовый результат score
            mtf_data: MTF данные

        Returns:
            Скорректированный ScoreResult
        """
        # Создаём копию результата
        enhanced_result = ScoreResult(
            symbol=base_result.symbol,
            timeframe=base_result.timeframe,
            ts=base_result.ts,
            score_raw=base_result.score_raw,
            score_calibrated=base_result.score_calibrated,
            p_win=base_result.p_win,
            edge_net=base_result.edge_net,
            confidence=base_result.confidence,
            is_valid=base_result.is_valid,
            reasons=base_result.reasons,
        )

        # Корректируем score_calibrated на основе MTF consensus
        if base_result.score_calibrated is not None and mtf_data.consensus != 0:
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # MTF корректировка: увеличиваем score при совпадении направления
            base_score = float(base_result.score_calibrated)

            if mtf_data.consensus == 1:  # MTF LONG
                # Увеличиваем score для LONG позиций
                mtf_boost = mtf_confidence * self.mtf_weight
                enhanced_score = min(1.0, base_score + mtf_boost)
            elif mtf_data.consensus == -1:  # MTF SHORT
                # Уменьшаем score для SHORT позиций (инвертируем)
                mtf_boost = mtf_confidence * self.mtf_weight
                enhanced_score = max(0.0, base_score - mtf_boost)
            else:  # MTF FLAT
                # Незначительная корректировка
                enhanced_score = base_score

            enhanced_result.score_calibrated = Decimal(str(enhanced_score))

            self.logger.info(
                f"MTF корректировка score: {base_score:.3f} -> {enhanced_score:.3f}"
            )

        # Корректируем p_win на основе MTF уверенности
        if base_result.p_win is not None:
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # Увеличиваем p_win при высокой MTF уверенности
            base_p_win = float(base_result.p_win)
            mtf_boost = mtf_confidence * self.mtf_weight * 0.2  # Максимум +20%
            enhanced_p_win = min(1.0, base_p_win + mtf_boost)

            enhanced_result.p_win = Decimal(str(enhanced_p_win))

            self.logger.info(
                f"MTF корректировка p_win: {base_p_win:.3f} -> {enhanced_p_win:.3f}"
            )

        # Корректируем edge_net на основе MTF context_score
        if base_result.edge_net is not None and mtf_data.context_score is not None:
            base_edge = float(base_result.edge_net)

            # Увеличиваем edge при сильном MTF тренде
            context_boost = abs(mtf_data.context_score) * self.mtf_weight * 0.1
            enhanced_edge = base_edge + context_boost

            enhanced_result.edge_net = Decimal(str(enhanced_edge))

            self.logger.info(
                f"MTF корректировка edge_net: {base_edge:.3f} -> {enhanced_edge:.3f}"
            )

        # Корректируем confidence на основе MTF силы
        if base_result.confidence is not None:
            base_confidence = float(base_result.confidence)
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # Увеличиваем confidence при сильном MTF сигнале
            confidence_boost = mtf_confidence * self.mtf_weight * 0.3
            enhanced_confidence = min(1.0, base_confidence + confidence_boost)

            enhanced_result.confidence = Decimal(str(enhanced_confidence))

            self.logger.info(
                f"MTF корректировка confidence: {base_confidence:.3f} -> {enhanced_confidence:.3f}"
            )

        return enhanced_result

    async def get_mtf_enhanced_scores(
        self, symbols: list, timeframe: str, use_mtf: bool = True
    ) -> dict[str, ScoreResult]:
        """
        Получает MTF-улучшенные scores для списка символов

        Args:
            symbols: Список символов
            timeframe: Таймфрейм
            use_mtf: Использовать ли MTF данные

        Returns:
            Словарь {symbol: ScoreResult}
        """
        results = {}

        for symbol in symbols:
            try:
                # Получаем последний timestamp для символа
                async for session in get_async_session():
                    query = text(
                        """
                        SELECT MAX(ts) as latest_ts
                        FROM indicators
                        WHERE symbol = :symbol AND timeframe = :timeframe
                    """
                    )
                    result = await session.execute(
                        query, {"symbol": symbol, "timeframe": timeframe}
                    )
                    row = result.fetchone()

                    if row and row.latest_ts:
                        score_result = await self.compute_score_with_mtf(
                            symbol, timeframe, row.latest_ts, use_mtf
                        )
                        if score_result:
                            results[symbol] = score_result
                    break

            except Exception as e:
                self.logger.error(f"Ошибка при получении MTF score для {symbol}: {e}")
                continue

        self.logger.info(
            f"Получено {len(results)} MTF-улучшенных scores из {len(symbols)} символов"
        )
        return results

    async def validate_mtf_score_alignment(
        self, symbol: str, score_result: ScoreResult, min_confidence: float = 0.4
    ) -> dict[str, Any]:
        """
        Проверяет соответствие score MTF сигналу

        Args:
            symbol: Торговый символ
            score_result: Результат score
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
                    "score_direction": "UNKNOWN",
                }

            # Определяем направление score
            if score_result.score_calibrated is None:
                score_direction = "UNKNOWN"
            elif float(score_result.score_calibrated) > 0.6:
                score_direction = "LONG"
            elif float(score_result.score_calibrated) < 0.4:
                score_direction = "SHORT"
            else:
                score_direction = "FLAT"

            mtf_direction = mtf_integrator.get_mtf_direction(mtf_data)
            mtf_confidence = mtf_integrator.calculate_mtf_confidence(mtf_data)

            # Проверяем соответствие направления
            is_aligned = (
                (score_direction == "LONG" and mtf_direction == "LONG")
                or (score_direction == "SHORT" and mtf_direction == "SHORT")
                or (score_direction == "FLAT" and mtf_direction == "FLAT")
            )

            # Проверяем уверенность
            is_confident = mtf_confidence >= min_confidence

            return {
                "is_aligned": is_aligned and is_confident,
                "reason": f"Score: {score_direction}, MTF: {mtf_direction} (confidence: {mtf_confidence:.3f})",
                "score_direction": score_direction,
                "mtf_direction": mtf_direction,
                "mtf_confidence": mtf_confidence,
                "score_value": (
                    float(score_result.score_calibrated)
                    if score_result.score_calibrated
                    else None
                ),
                "mtf_context_score": mtf_data.context_score,
            }

        except Exception as e:
            self.logger.error(f"Ошибка при MTF валидации score для {symbol}: {e}")
            return {
                "is_aligned": False,
                "reason": f"Ошибка MTF валидации: {e}",
                "score_direction": "ERROR",
                "mtf_direction": "ERROR",
            }


# Глобальный экземпляр MTF-улучшенного scoring engine
mtf_scoring_engine = MTFEnhancedScoringEngine()
