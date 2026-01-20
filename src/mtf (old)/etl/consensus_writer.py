"""
ETL модуль для записи финальных решений consensus

Читает данные из mtf.context и mtf.triggers, собирает input_data,
рассчитывает horizon-решения и записывает в mtf.consensus
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.database import get_async_session

logger = logging.getLogger(__name__)


class ConsensusWriter:
    """Записыватель финальных решений для MTF"""

    # Поддерживаемые горизонты
    HORIZONS = ["intraday", "swing", "week"]

    # Весовые формулы для каждого горизонта (используем реальные названия TF)
    HORIZON_WEIGHTS = {
        "intraday": {"1Dutc": 0.5, "4H": 0.3, "15m": 0.2},
        "swing": {"1Dutc": 0.4, "4H": 0.3, "1Wutc": 0.2, "15m": 0.1},
        "week": {"1Dutc": 0.4, "1Wutc": 0.3, "1Mutc": 0.3},
    }

    # Пороги для принятия решений (снижены для лучшего покрытия)
    DECISION_THRESHOLDS = {
        "intraday": {"p15_min": 0.52, "p5_min": 0.51, "micro_required": False},
        "swing": {
            "p15_min": 0.55,
            "confirmations_required": 1,
            "micro_required": False,
        },
        "week": {"p15_min": 0.58, "conflict_max": 0.3, "micro_required": False},
    }

    # Веса для расчета итогового score
    SCORE_WEIGHTS = {
        "context": 0.4,
        "trigger": 0.4,
        "volume": 0.1,
        "liquidity": 0.1,
        "risk": 0.1,
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def write_consensus_for_symbol(
        self, symbol: str, horizons: list[str] | None = None
    ) -> bool:
        """
        Записывает consensus для одного символа

        Args:
            symbol: Торговый символ
            horizons: Список горизонтов для расчета (по умолчанию все)

        Returns:
            True если данные записаны успешно
        """
        try:
            if horizons is None:
                horizons = self.HORIZONS

            async for session in get_async_session():
                # Получаем контекстные данные
                context_data = await self._get_context_data(session, symbol)
                if not context_data:
                    self.logger.warning(f"Нет контекстных данных для {symbol}")
                    return False

                # Получаем триггерные данные
                trigger_data = await self._get_trigger_data(session, symbol)
                if not trigger_data:
                    self.logger.warning(f"Нет триггерных данных для {symbol}")
                    return False

                # Рассчитываем consensus для каждого горизонта
                consensus_data = []
                for horizon in horizons:
                    consensus = await self._calculate_consensus(
                        session, symbol, horizon, context_data, trigger_data
                    )
                    if consensus:
                        consensus_data.append(consensus)

                # Сохраняем в mtf.consensus
                if consensus_data:
                    await self._save_consensus_data(session, consensus_data)
                    self.logger.info(
                        f"Записан consensus для {symbol}: {len(consensus_data)} горизонтов"
                    )
                    return True

                return False

        except Exception as e:
            self.logger.error(f"Ошибка записи consensus для {symbol}: {e}")
            return False

    async def write_consensus_for_all_symbols(
        self, horizons: list[str] | None = None
    ) -> dict[str, bool]:
        """
        Записывает consensus для всех символов

        Args:
            horizons: Список горизонтов для расчета (по умолчанию все)

        Returns:
            Словарь {symbol: success}
        """
        try:
            if horizons is None:
                horizons = self.HORIZONS

            async for session in get_async_session():
                # Получаем список всех символов
                symbols = await self._get_all_symbols(session)

                results = {}
                for symbol in symbols:
                    success = await self.write_consensus_for_symbol(symbol, horizons)
                    results[symbol] = success

                self.logger.info(
                    f"Запись consensus завершена: {sum(results.values())}/{len(results)} успешно"
                )
                return results

        except Exception as e:
            self.logger.error(f"Ошибка массовой записи consensus: {e}")
            return {}

    async def _get_context_data(self, session, symbol: str) -> dict[str, Any]:
        """Получает контекстные данные для символа"""
        query = text(
            """
            SELECT timeframe, ts, score, valid, regime, meta
            FROM mtf.context
            WHERE symbol = :symbol
            ORDER BY timeframe, ts DESC
        """
        )

        result = await session.execute(query, {"symbol": symbol})

        context_data = {}
        for row in result.fetchall():
            tf = row.timeframe
            if tf not in context_data:
                context_data[tf] = row._asdict()

        return context_data

    async def _get_trigger_data(self, session, symbol: str) -> dict[str, Any]:
        """Получает триггерные данные для символа"""
        query = text(
            """
            SELECT timeframe, ts, p_up, p_down, accel, micro_ok, features
            FROM mtf.triggers
            WHERE symbol = :symbol
            ORDER BY timeframe, ts DESC
        """
        )

        result = await session.execute(query, {"symbol": symbol})

        trigger_data = {}
        for row in result.fetchall():
            tf = row.timeframe
            if tf not in trigger_data:
                trigger_data[tf] = row._asdict()

        return trigger_data

    async def _calculate_consensus(
        self, session, symbol: str, horizon: str, context_data: dict, trigger_data: dict
    ) -> dict | None:
        """Рассчитывает consensus для одного горизонта"""
        try:
            # Рассчитываем context score для горизонта
            context_score = self._calculate_horizon_context(horizon, context_data)

            # Получаем триггерные данные
            p15_up = trigger_data.get("15m", {}).get("p_up", 0.5)
            p15_down = trigger_data.get("15m", {}).get("p_down", 0.5)
            p5_up = trigger_data.get("5m", {}).get("p_up", 0.5)
            p5_down = trigger_data.get("5m", {}).get("p_down", 0.5)
            accel_5m = trigger_data.get("5m", {}).get("accel", 0)
            micro_ok = trigger_data.get("1m", {}).get("micro_ok", True)

            # Определяем bias
            bias = self._determine_bias(context_score)

            # Применяем правила принятия решения
            side = self._apply_decision_rules(
                horizon,
                bias,
                p15_up,
                p15_down,
                p5_up,
                p5_down,
                accel_5m,
                micro_ok,
                context_data,
            )

            # Рассчитываем итоговый score
            final_score = self._calculate_final_score(
                horizon,
                context_score,
                bias,
                p15_up,
                p15_down,
                p5_up,
                p5_down,
                context_data,
                trigger_data,
            )

            # Формируем input_data с конвертацией Decimal в float
            input_data = {
                "horizon": horizon,
                "context_score": context_score,
                "bias": bias,
                "p15_up": float(p15_up) if hasattr(p15_up, "__float__") else p15_up,
                "p15_down": (
                    float(p15_down) if hasattr(p15_down, "__float__") else p15_down
                ),
                "p5_up": float(p5_up) if hasattr(p5_up, "__float__") else p5_up,
                "p5_down": float(p5_down) if hasattr(p5_down, "__float__") else p5_down,
                "accel_5m": accel_5m,
                "micro_ok": micro_ok,
                "context_data": self._convert_decimal_dict(context_data),
                "trigger_data": self._convert_decimal_dict(trigger_data),
                "decision_rules": self.DECISION_THRESHOLDS.get(horizon, {}),
                "calculated_at": datetime.utcnow().isoformat(),
            }

            return {
                "symbol": symbol,
                "horizon": horizon,
                "ts": datetime.utcnow(),
                "side": side,
                "score": final_score,
                "input_data": json.dumps(input_data),
            }

        except Exception as e:
            self.logger.error(f"Ошибка расчета consensus для {symbol} {horizon}: {e}")
            return None

    def _calculate_horizon_context(self, horizon: str, context_data: dict) -> float:
        """Рассчитывает context score для конкретного горизонта"""
        try:
            weights = self.HORIZON_WEIGHTS.get(horizon, {})
            context_score = 0.0

            for tf, weight in weights.items():
                if tf in context_data:
                    score = context_data[tf].get("score", 0.0)
                    # Конвертируем Decimal в float
                    if hasattr(score, "__float__"):
                        score = float(score)
                    context_score += score * weight

            return context_score

        except Exception as e:
            self.logger.error(f"Ошибка расчета context score для {horizon}: {e}")
            return 0.0

    def _determine_bias(self, context_score: float) -> str:
        """Определяет bias на основе context score"""
        if context_score > 0.1:
            return "long"
        if context_score < -0.1:
            return "short"
        return "neutral"

    def _convert_decimal_dict(self, data: Any) -> Any:
        """Конвертирует Decimal и datetime в JSON-совместимые типы"""
        if isinstance(data, dict):
            return {k: self._convert_decimal_dict(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._convert_decimal_dict(item) for item in data]
        if hasattr(data, "__float__"):
            return float(data)
        if isinstance(data, datetime):
            return data.isoformat()
        return data

    def _apply_decision_rules(
        self,
        horizon: str,
        bias: str,
        p15_up: float,
        p15_down: float,
        p5_up: float,
        p5_down: float,
        accel_5m: int,
        micro_ok: bool,
        context_data: dict,
    ) -> int:
        """Применяет правила принятия решения для горизонта"""
        try:
            thresholds = self.DECISION_THRESHOLDS.get(horizon, {})

            # Конвертируем Decimal в float
            if hasattr(p15_up, "__float__"):
                p15_up = float(p15_up)
            if hasattr(p15_down, "__float__"):
                p15_down = float(p15_down)
            if hasattr(p5_up, "__float__"):
                p5_up = float(p5_up)
            if hasattr(p5_down, "__float__"):
                p5_down = float(p5_down)

            if horizon == "intraday":
                # Правила для intraday
                if bias == "long" and p15_up >= thresholds.get("p15_min", 0.6):
                    if p5_up >= thresholds.get("p5_min", 0.55) or accel_5m == 1:
                        if not thresholds.get("micro_required", True) or micro_ok:
                            return 1  # LONG

                elif bias == "short" and p15_down >= thresholds.get("p15_min", 0.6):
                    if p5_down >= thresholds.get("p5_min", 0.55) or accel_5m == -1:
                        if not thresholds.get("micro_required", True) or micro_ok:
                            return -1  # SHORT

                return 0  # FLAT

            if horizon == "swing":
                # Правила для swing
                if bias == "long" and p15_up >= thresholds.get("p15_min", 0.62):
                    # Проверяем подтверждения (упрощенно)
                    confirmations = 0
                    if p5_up >= 0.55:
                        confirmations += 1
                    if accel_5m == 1:
                        confirmations += 1

                    if confirmations >= thresholds.get("confirmations_required", 2):
                        return 1  # LONG

                elif bias == "short" and p15_down >= thresholds.get("p15_min", 0.62):
                    confirmations = 0
                    if p5_down >= 0.55:
                        confirmations += 1
                    if accel_5m == -1:
                        confirmations += 1

                    if confirmations >= thresholds.get("confirmations_required", 2):
                        return -1  # SHORT

                return 0  # FLAT

            if horizon == "week":
                # Правила для week
                if bias == "long" and p15_up >= thresholds.get("p15_min", 0.65):
                    # Проверяем отсутствие сильных конфликтов
                    conflict_level = self._calculate_conflict_level(
                        context_data, "long"
                    )
                    if conflict_level <= thresholds.get("conflict_max", 0.2):
                        return 1  # LONG

                elif bias == "short" and p15_down >= thresholds.get("p15_min", 0.65):
                    conflict_level = self._calculate_conflict_level(
                        context_data, "short"
                    )
                    if conflict_level <= thresholds.get("conflict_max", 0.2):
                        return -1  # SHORT

                return 0  # FLAT

            return 0  # FLAT по умолчанию

        except Exception as e:
            self.logger.error(f"Ошибка применения правил решения для {horizon}: {e}")
            return 0

    def _calculate_conflict_level(self, context_data: dict, bias: str) -> float:
        """Рассчитывает уровень конфликтов"""
        try:
            conflicts = 0
            total_weight = 0

            for _tf, data in context_data.items():
                score = data.get("score", 0.0)
                # Конвертируем Decimal в float
                if hasattr(score, "__float__"):
                    score = float(score)
                weight = 1.0  # Можно настроить веса по TF

                if bias == "long" and score < 0 or bias == "short" and score > 0:
                    conflicts += abs(score) * weight

                total_weight += weight

            return conflicts / total_weight if total_weight > 0 else 0.0

        except Exception as e:
            self.logger.error(f"Ошибка расчета уровня конфликтов: {e}")
            return 0.0

    def _calculate_final_score(
        self,
        horizon: str,
        context_score: float,
        bias: str,
        p15_up: float,
        p15_down: float,
        p5_up: float,
        p5_down: float,
        context_data: dict,
        trigger_data: dict,
    ) -> float:
        """Рассчитывает итоговый score для ранжирования"""
        try:
            # Конвертируем Decimal в float
            if hasattr(p15_up, "__float__"):
                p15_up = float(p15_up)
            if hasattr(p15_down, "__float__"):
                p15_down = float(p15_down)
            if hasattr(p5_up, "__float__"):
                p5_up = float(p5_up)
            if hasattr(p5_down, "__float__"):
                p5_down = float(p5_down)

            # Context компонент (40% веса)
            context_norm = abs(context_score)
            context_score_component = context_norm * 0.4

            # Trigger компонент (40% веса)
            if bias == "long":
                trig_prob = 0.7 * p15_up + 0.3 * p5_up
            elif bias == "short":
                trig_prob = 0.7 * p15_down + 0.3 * p5_down
            else:
                trig_prob = 0.5

            trigger_score_component = trig_prob * 0.4

            # Дополнительные компоненты (20% веса)
            # Учитываем силу сигнала
            signal_strength = 0.0
            if bias == "long":
                signal_strength = max(p15_up, p5_up)
            elif bias == "short":
                signal_strength = max(p15_down, p5_down)

            additional_component = signal_strength * 0.2

            # Итоговый score
            final_score = (
                context_score_component + trigger_score_component + additional_component
            )

            # Нормализуем и добавляем базовый уровень
            return max(0.1, min(0.95, final_score))

        except Exception as e:
            self.logger.error(f"Ошибка расчета итогового score: {e}")
            return 0.3

    async def _save_consensus_data(self, session, consensus_data: list[dict]) -> None:
        """Сохраняет consensus данные в mtf.consensus"""
        for consensus in consensus_data:
            query = text(
                """
                INSERT INTO mtf.consensus (symbol, horizon, ts, side, score, input_data)
                VALUES (:symbol, :horizon, :ts, :side, :score, :input_data)
            """
            )

            await session.execute(query, consensus)

        await session.commit()

    async def _get_all_symbols(self, session) -> list[str]:
        """Получает список всех символов из mtf.context"""
        query = text(
            """
            SELECT DISTINCT symbol
            FROM mtf.context
            ORDER BY symbol
        """
        )

        result = await session.execute(query)
        return [row[0] for row in result.fetchall()]


# Глобальный экземпляр записывателя
consensus_writer = ConsensusWriter()
