"""
Основной модуль для вычисления score
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.models import CombinationResult, Indicator

from .models import ScoreResult as ScoreResultModel

logger = logging.getLogger(__name__)


@dataclass
class ScoreResult:
    """Результат вычисления score"""

    symbol: str
    timeframe: str
    ts: int
    score_raw: float
    score_calibrated: float
    p_win: float
    edge_net: float
    confidence: float
    is_valid: bool
    reasons: list[str]


class ScoringEngine:
    """Движок для вычисления score"""

    def __init__(self, config_path: str | None = None):
        """Инициализация с конфигурацией"""
        if config_path is None:
            config_path = Path(__file__).parent / "weights_extended.yaml"

        with open(config_path, encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.weights = self.config["indicators"]
        self.combination_weights = self.config["combinations"]
        self.normalization = self.config["normalization"]
        self.trading_params = self.config["trading"]

    def normalize_value(self, value: float, indicator_name: str) -> float:
        """Приводит значение к диапазону [0;1]"""
        if value is None:
            return 0.5  # Нейтральное значение при отсутствии данных

        bounds = self.normalization.get(indicator_name, {"min": 0, "max": 1})
        min_val = bounds["min"]
        max_val = bounds["max"]

        # Ограничиваем значение границами
        value = max(min_val, min(max_val, value))

        # Нормализуем к [0;1]
        if max_val == min_val:
            return 0.5

        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    def get_indicator_value(
        self, indicator_data: dict[str, Any], indicator_name: str
    ) -> float:
        """Извлекает и нормализует значение индикатора"""
        value = indicator_data.get(indicator_name)
        if value is None:
            return 0.5

        # Специальная обработка для относительных индикаторов (отношение к цене)
        relative_indicators = [
            # Moving Averages
            "ema12",
            "ema21",
            "ema26",
            "ema50",
            "ema200",
            "sma50",
            "sma200",
            "ema_8",
            "ema_13",
            "ema_34",
            "ema_55",
            "ema_89",
            "ema_144",
            "ema_233",
            # Волатильность
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "kc_upper",
            "kc_middle",
            "kc_lower",
            # Объемные
            "vwap",
            "vp_value_area_high",
            "vp_value_area_low",
            "vp_point_of_control",
            # Ichimoku
            "ichimoku_tenkan",
            "ichimoku_kijun",
            "ichimoku_senkou_a",
            "ichimoku_senkou_b",
            "ichimoku_chikou",
        ]

        if indicator_name in relative_indicators:
            close = indicator_data.get("close", 1.0)
            if close and value:
                return close / value
            return 0.5

        return self.normalize_value(value, indicator_name)

    def get_combination_value(
        self, combination_data: dict[str, Any], combination_name: str
    ) -> float:
        """Извлекает значение комбинации"""
        signal_strength = combination_data.get("signal_strength")
        if signal_strength is None:
            return 0.5

        return max(0.0, min(1.0, signal_strength))

    async def get_latest_data(
        self, session: AsyncSession, symbol: str, timeframe: str, ts: int
    ) -> tuple[dict | None, dict | None]:
        """Получает последние данные индикаторов и комбинаций"""
        try:
            # Получаем данные индикаторов
            indicator_query = select(Indicator).where(
                Indicator.symbol == symbol,
                Indicator.timeframe == timeframe,
                Indicator.ts == ts,
            )
            indicator_result = await session.execute(indicator_query)
            indicator_row = indicator_result.scalar_one_or_none()

            if not indicator_row:
                return None, None

            indicator_data = self._extract_indicator_data(indicator_row)
            combination_data = await self._extract_combination_data(
                session, symbol, timeframe, ts
            )

            return indicator_data, combination_data

        except Exception as e:
            logger.error(f"Ошибка при получении данных: {e}")
            return None, None

    def _extract_indicator_data(self, indicator_row) -> dict[str, Any]:
        """Извлекает данные индикаторов из строки БД"""
        # Базовые данные
        data = {
            "close": float(indicator_row.close) if indicator_row.close else None,
        }

        # Осцилляторы
        osc_indicators = [
            "rsi14",
            "stoch_k",
            "stoch_d",
            "macd",
            "macd_signal",
            "macd_histogram",
        ]
        for indicator in osc_indicators:
            if hasattr(indicator_row, indicator):
                value = getattr(indicator_row, indicator)
                data[indicator] = float(value) if value is not None else None

        # Трендовые индикаторы
        trend_indicators = ["adx14", "adx_pos_di", "adx_neg_di"]
        for indicator in trend_indicators:
            if hasattr(indicator_row, indicator):
                value = getattr(indicator_row, indicator)
                data[indicator] = float(value) if value is not None else None

        # Moving Averages
        ma_indicators = [
            "ema12",
            "ema21",
            "ema26",
            "ema50",
            "ema200",
            "sma50",
            "sma200",
            "ema_8",
            "ema_13",
            "ema_34",
            "ema_55",
            "ema_89",
            "ema_144",
            "ema_233",
        ]
        for indicator in ma_indicators:
            if hasattr(indicator_row, indicator):
                value = getattr(indicator_row, indicator)
                data[indicator] = float(value) if value is not None else None

        # Волатильность
        vol_indicators = [
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "kc_upper",
            "kc_middle",
            "kc_lower",
            "atr14",
        ]
        for indicator in vol_indicators:
            if hasattr(indicator_row, indicator):
                value = getattr(indicator_row, indicator)
                data[indicator] = float(value) if value is not None else None

        # Объемные индикаторы
        volume_indicators = [
            "obv",
            "cmf",
            "vwap",
            "vp_value_area_high",
            "vp_value_area_low",
            "vp_point_of_control",
            "volume_sma20",
        ]
        for indicator in volume_indicators:
            if hasattr(indicator_row, indicator):
                value = getattr(indicator_row, indicator)
                data[indicator] = float(value) if value is not None else None

        # Ichimoku
        ichimoku_indicators = [
            "ichimoku_tenkan",
            "ichimoku_kijun",
            "ichimoku_senkou_a",
            "ichimoku_senkou_b",
            "ichimoku_chikou",
        ]
        for indicator in ichimoku_indicators:
            if hasattr(indicator_row, indicator):
                value = getattr(indicator_row, indicator)
                data[indicator] = float(value) if value is not None else None

        return data

    async def _extract_combination_data(
        self, session: AsyncSession, symbol: str, timeframe: str, ts: int
    ) -> dict[str, Any]:
        """Извлекает данные комбинаций из БД"""
        combination_query = select(CombinationResult).where(
            CombinationResult.symbol == symbol,
            CombinationResult.timeframe == timeframe,
            CombinationResult.ts == ts,
        )
        combination_result = await session.execute(combination_query)
        combination_rows = combination_result.scalars().all()

        combination_data = {}
        for row in combination_rows:
            combination_data[row.combination_name] = {
                "signal_strength": (
                    float(row.signal_strength) if row.signal_strength else None
                ),
                "agreement_count": row.agreement_count,
                "conflict_count": row.conflict_count,
            }

        return combination_data

    def compute_score_raw(
        self, indicator_data: dict, combination_data: dict
    ) -> tuple[float, list[str]]:
        """Вычисляет сырой score и причины отклонения"""
        reasons = []
        total_score = 0.0
        total_weight = 0.0

        # Обрабатываем индикаторы
        for indicator_name, weight in self.weights.items():
            if (
                indicator_name not in indicator_data
                or indicator_data[indicator_name] is None
            ):
                reasons.append(f"Отсутствует индикатор: {indicator_name}")
                continue

            value = self.get_indicator_value(indicator_data, indicator_name)
            total_score += weight * value
            total_weight += weight

        # Обрабатываем комбинации
        for combination_name, weight in self.combination_weights.items():
            if combination_name not in combination_data:
                reasons.append(f"Отсутствует комбинация: {combination_name}")
                continue

            value = self.get_combination_value(
                combination_data[combination_name], combination_name
            )
            total_score += weight * value
            total_weight += weight

        # Проверяем достаточность данных
        if total_weight < 0.5:  # Минимальный вес для валидного результата
            reasons.append(f"Недостаточно данных: total_weight={total_weight:.3f}")
            return 0.5, reasons

        # Нормализуем score
        score_raw = total_score / total_weight if total_weight > 0 else 0.5

        return score_raw, reasons

    def calibrate_score(self, score_raw: float) -> float:
        """Калибрует score (пока просто возвращает сырой score)"""
        # TODO: В будущем здесь будет простая линейная модель по историческим hitrate
        return score_raw

    def calculate_metrics(self, score_calibrated: float) -> tuple[float, float, float]:
        """Вычисляет дополнительные метрики"""
        # p_win = score_calibrated
        p_win = score_calibrated

        # confidence = abs(score_raw - 0.5) * 2
        confidence = abs(score_calibrated - 0.5) * 2

        # edge_net = (p_win - 0.5) × RR - cost
        RR = self.trading_params["reward_risk_ratio"]
        cost = self.trading_params["cost"]
        edge_net = (p_win - 0.5) * RR - cost

        return p_win, edge_net, confidence

    async def compute_score(
        self, symbol: str, timeframe: str, ts: int
    ) -> ScoreResult | None:
        """Основная функция вычисления score"""
        try:
            async for session in get_async_session():
                try:
                    # Получаем данные
                    indicator_data, combination_data = await self.get_latest_data(
                        session, symbol, timeframe, ts
                    )

                    if not indicator_data:
                        logger.warning(f"Нет данных для {symbol} {timeframe} {ts}")
                        return None

                    # Вычисляем сырой score
                    score_raw, reasons = self.compute_score_raw(
                        indicator_data, combination_data
                    )

                    # Определяем валидность
                    is_valid = len(reasons) == 0

                    # Калибруем score
                    score_calibrated = self.calibrate_score(score_raw)

                    # Вычисляем метрики
                    p_win, edge_net, confidence = self.calculate_metrics(
                        score_calibrated
                    )

                    # Создаем результат
                    result = ScoreResult(
                        symbol=symbol,
                        timeframe=timeframe,
                        ts=ts,
                        score_raw=score_raw,
                        score_calibrated=score_calibrated,
                        p_win=p_win,
                        edge_net=edge_net,
                        confidence=confidence,
                        is_valid=is_valid,
                        reasons=reasons,
                    )

                    # Сохраняем в БД
                    await self.save_score_result(session, result)

                    return result

                except Exception as e:
                    logger.error(
                        f"Ошибка при вычислении score для {symbol} {timeframe} {ts}: {e}"
                    )
                    await session.rollback()
                    return None
                finally:
                    await session.close()

        except Exception as e:
            logger.error(
                f"Критическая ошибка при создании сессии для {symbol} {timeframe} {ts}: {e}"
            )
            return None

    async def save_score_result(self, session: AsyncSession, result: ScoreResult):
        """Сохраняет результат в БД"""
        try:
            # Проверяем, существует ли уже запись
            existing_query = select(ScoreResultModel).where(
                ScoreResultModel.symbol == result.symbol,
                ScoreResultModel.timeframe == result.timeframe,
                ScoreResultModel.ts == result.ts,
            )
            existing_result = await session.execute(existing_query)
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Обновляем существующую запись
                self._update_existing_score(existing, result)
            else:
                # Создаем новую запись
                db_result = self._create_new_score_result(result)
                session.add(db_result)

            await session.commit()
            logger.info(
                f"Сохранен score для {result.symbol} {result.timeframe} {result.ts}"
            )

        except Exception as e:
            logger.error(f"Ошибка при сохранении score: {e}")
            await session.rollback()
            raise

    def _update_existing_score(self, existing, result: ScoreResult):
        """Обновляет существующую запись score"""
        existing.score_raw = result.score_raw
        existing.score_calibrated = result.score_calibrated
        existing.p_win = result.p_win
        existing.edge_net = result.edge_net
        existing.confidence = result.confidence
        existing.is_valid = result.is_valid
        existing.reasons = result.reasons
        existing.updated_at = datetime.utcnow()

    def _create_new_score_result(self, result: ScoreResult) -> ScoreResultModel:
        """Создает новую запись score"""
        return ScoreResultModel(
            symbol=result.symbol,
            timeframe=result.timeframe,
            ts=result.ts,
            score_raw=result.score_raw,
            score_calibrated=result.score_calibrated,
            p_win=result.p_win,
            edge_net=result.edge_net,
            confidence=result.confidence,
            is_valid=result.is_valid,
            reasons=result.reasons,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )


# Глобальный экземпляр движка
_engine = None


def get_scoring_engine() -> ScoringEngine:
    """Возвращает глобальный экземпляр движка"""
    global _engine
    if _engine is None:
        _engine = ScoringEngine()
    return _engine


async def compute_score(symbol: str, timeframe: str, ts: int) -> ScoreResult | None:
    """Удобная функция для вычисления score"""
    engine = get_scoring_engine()
    return await engine.compute_score(symbol, timeframe, ts)
