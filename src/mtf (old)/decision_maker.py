#!/usr/bin/env python3
"""
MTF Decision Maker - Модуль для принятия торговых решений

Предоставляет читаемый интерфейс для анализа MTF данных и принятия решений
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import text

from src.database import get_async_session

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Типы торговых сигналов"""

    LONG = 1
    SHORT = -1
    FLAT = 0


class ConfidenceLevel(Enum):
    """Уровни уверенности"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TimeframeAnalysis:
    """Анализ одного таймфрейма"""

    timeframe: str
    score: float
    valid: bool
    regime: str | None
    confidence: ConfidenceLevel
    description: str


@dataclass
class TriggerAnalysis:
    """Анализ триггерных данных"""

    timeframe: str
    p_up: float
    p_down: float
    accel: int | None
    micro_ok: bool | None
    confidence: ConfidenceLevel
    description: str


@dataclass
class ConsensusAnalysis:
    """Анализ consensus данных"""

    horizon: str
    side: SignalType
    score: float
    confidence: ConfidenceLevel
    description: str


@dataclass
class TradingDecision:
    """Финальное торговое решение"""

    symbol: str
    timestamp: datetime
    decision: SignalType
    confidence: ConfidenceLevel
    horizon: str
    reasoning: list[str]
    context_analysis: list[TimeframeAnalysis]
    trigger_analysis: list[TriggerAnalysis]
    consensus_analysis: ConsensusAnalysis
    risk_level: str
    entry_conditions: list[str]
    exit_conditions: list[str]


class MTFDecisionMaker:
    """Система принятия решений на основе MTF анализа"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Пороги для уровней уверенности
        self.CONFIDENCE_THRESHOLDS = {
            ConfidenceLevel.HIGH: 0.7,
            ConfidenceLevel.MEDIUM: 0.4,
            ConfidenceLevel.LOW: 0.0,
        }

        # Описания режимов
        self.REGIME_DESCRIPTIONS = {
            "trend_bull": "Сильный восходящий тренд",
            "trend_bear": "Сильный нисходящий тренд",
            "range_bull": "Боковик с бычьим уклоном",
            "range_bear": "Боковик с медвежьим уклоном",
        }

        # Описания ускорений
        self.ACCEL_DESCRIPTIONS = {
            1: "Положительное ускорение",
            0: "Нейтральное ускорение",
            -1: "Отрицательное ускорение",
        }

    async def analyze_symbol(self, symbol: str) -> TradingDecision:
        """Полный анализ символа для принятия решения"""
        try:
            async for session in get_async_session():
                # Получаем все данные
                context_data = await self._get_context_data(session, symbol)
                trigger_data = await self._get_trigger_data(session, symbol)
                consensus_data = await self._get_consensus_data(session, symbol)

                # Анализируем каждый компонент
                context_analysis = self._analyze_context(context_data)
                trigger_analysis = self._analyze_triggers(trigger_data)
                consensus_analysis = self._analyze_consensus(consensus_data)

                # Принимаем решение
                decision = self._make_decision(
                    context_analysis, trigger_analysis, consensus_analysis
                )

                # Формируем финальное решение
                return TradingDecision(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    decision=decision["signal"],
                    confidence=decision["confidence"],
                    horizon=decision["horizon"],
                    reasoning=decision["reasoning"],
                    context_analysis=context_analysis,
                    trigger_analysis=trigger_analysis,
                    consensus_analysis=consensus_analysis,
                    risk_level=decision["risk_level"],
                    entry_conditions=decision["entry_conditions"],
                    exit_conditions=decision["exit_conditions"],
                )

        except Exception as e:
            self.logger.error(f"Ошибка анализа {symbol}: {e}")
            raise

    async def get_market_overview(self, limit: int = 20) -> list[dict]:
        """Обзор рынка - топ сигналов"""
        try:
            async for session in get_async_session():
                query = text(
                    """
                    SELECT
                        c.symbol,
                        c.horizon,
                        c.side,
                        c.score,
                        c.ts
                    FROM mtf.consensus c
                    WHERE c.score > 0.3
                    ORDER BY c.score DESC, c.ts DESC
                    LIMIT :limit
                """
                )

                result = await session.execute(query, {"limit": limit})
                rows = result.fetchall()

                # Преобразуем в словари с добавлением signal_type
                data = []
                for row in rows:
                    row_dict = {
                        "symbol": row.symbol,
                        "horizon": row.horizon,
                        "side": row.side,
                        "score": row.score,
                        "ts": row.ts,
                    }
                    # Добавляем signal_type
                    if row.side == 1:
                        row_dict["signal_type"] = "LONG"
                    elif row.side == -1:
                        row_dict["signal_type"] = "SHORT"
                    else:
                        row_dict["signal_type"] = "FLAT"
                    data.append(row_dict)

                return data

        except Exception as e:
            self.logger.error(f"Ошибка получения обзора рынка: {e}")
            return []

    async def get_swing_opportunities(self) -> list[dict]:
        """Поиск swing торговых возможностей"""
        try:
            async for session in get_async_session():
                query = text(
                    """
                    SELECT
                        c.symbol,
                        c.side,
                        c.score,
                        c.ts,
                        ctx.score as context_score,
                        ctx.regime
                    FROM mtf.consensus c
                    JOIN mtf.context ctx ON c.symbol = ctx.symbol
                        AND ctx.timeframe = '1Dutc'
                    WHERE c.horizon = 'swing'
                        AND c.score > 0.4
                        AND ctx.valid = true
                    ORDER BY c.score DESC
                    LIMIT 10
                """
                )

                result = await session.execute(query)
                rows = result.fetchall()
                data = []
                for row in rows:
                    row_dict = {
                        "symbol": row.symbol,
                        "side": row.side,
                        "score": row.score,
                        "ts": row.ts,
                        "context_score": row.context_score,
                        "regime": row.regime,
                    }
                    data.append(row_dict)
                return data

        except Exception as e:
            self.logger.error(f"Ошибка поиска swing возможностей: {e}")
            return []

    async def get_intraday_signals(self) -> list[dict]:
        """Поиск внутридневных сигналов"""
        try:
            async for session in get_async_session():
                query = text(
                    """
                    SELECT
                        c.symbol,
                        c.side,
                        c.score,
                        c.ts,
                        t.p_up,
                        t.p_down,
                        t.accel
                    FROM mtf.consensus c
                    JOIN mtf.triggers t ON c.symbol = t.symbol
                        AND t.timeframe = '5m'
                    WHERE c.horizon = 'intraday'
                        AND c.score > 0.35
                    ORDER BY c.score DESC
                    LIMIT 15
                """
                )

                result = await session.execute(query)
                rows = result.fetchall()
                data = []
                for row in rows:
                    row_dict = {
                        "symbol": row.symbol,
                        "side": row.side,
                        "score": row.score,
                        "ts": row.ts,
                        "p_up": row.p_up,
                        "p_down": row.p_down,
                        "accel": row.accel,
                    }
                    data.append(row_dict)
                return data

        except Exception as e:
            self.logger.error(f"Ошибка поиска внутридневных сигналов: {e}")
            return []

    def _analyze_context(self, context_data: list[dict]) -> list[TimeframeAnalysis]:
        """Анализ контекстных данных"""
        analysis = []

        for data in context_data:
            score = float(data["score"]) if data["score"] is not None else 0.0
            valid = data["valid"]
            regime = data.get("regime")

            # Определяем уверенность
            confidence = self._get_confidence_level(abs(score))

            # Формируем описание
            description = self._get_context_description(
                data["timeframe"], score, valid, regime
            )

            analysis.append(
                TimeframeAnalysis(
                    timeframe=data["timeframe"],
                    score=score,
                    valid=valid,
                    regime=regime,
                    confidence=confidence,
                    description=description,
                )
            )

        return analysis

    def _analyze_triggers(self, trigger_data: list[dict]) -> list[TriggerAnalysis]:
        """Анализ триггерных данных"""
        analysis = []

        for data in trigger_data:
            p_up = float(data["p_up"]) if data["p_up"] is not None else 0.5
            p_down = float(data["p_down"]) if data["p_down"] is not None else 0.5
            accel = data.get("accel")
            micro_ok = data.get("micro_ok")

            # Определяем уверенность
            max_prob = max(p_up, p_down)
            confidence = self._get_confidence_level(max_prob)

            # Формируем описание
            description = self._get_trigger_description(
                data["timeframe"], p_up, p_down, accel, micro_ok
            )

            analysis.append(
                TriggerAnalysis(
                    timeframe=data["timeframe"],
                    p_up=p_up,
                    p_down=p_down,
                    accel=accel,
                    micro_ok=micro_ok,
                    confidence=confidence,
                    description=description,
                )
            )

        return analysis

    def _analyze_consensus(self, consensus_data: list[dict]) -> ConsensusAnalysis:
        """Анализ consensus данных"""
        if not consensus_data:
            return ConsensusAnalysis(
                horizon="unknown",
                side=SignalType.FLAT,
                score=0.0,
                confidence=ConfidenceLevel.LOW,
                description="Нет данных consensus",
            )

        data = consensus_data[0]  # Берем самый высокий score
        side = SignalType(data["side"])
        score = float(data["score"])
        horizon = data["horizon"]

        confidence = self._get_confidence_level(score)
        description = self._get_consensus_description(horizon, side, score)

        return ConsensusAnalysis(
            horizon=horizon,
            side=side,
            score=score,
            confidence=confidence,
            description=description,
        )

    def _make_decision(
        self,
        context_analysis: list[TimeframeAnalysis],
        trigger_analysis: list[TriggerAnalysis],
        consensus_analysis: ConsensusAnalysis,
    ) -> dict:
        """Принятие финального решения"""

        # Анализируем контекст
        sum([ctx.score for ctx in context_analysis if ctx.valid])
        context_conflicts = len([ctx for ctx in context_analysis if not ctx.valid])

        # Анализируем триггеры
        if trigger_analysis:
            sum([max(t.p_up, t.p_down) for t in trigger_analysis]) / len(
                trigger_analysis
            )

        # Анализируем consensus
        consensus_score = consensus_analysis.score
        consensus_side = consensus_analysis.side

        # Принимаем решение
        if consensus_score > 0.7 and context_conflicts <= 1:
            signal = consensus_side
            confidence = ConfidenceLevel.HIGH
            reasoning = [
                "Сильный consensus сигнал",
                "Минимальные конфликты в контексте",
            ]
        elif consensus_score > 0.5 and context_conflicts <= 2:
            signal = consensus_side
            confidence = ConfidenceLevel.MEDIUM
            reasoning = [
                "Умеренный consensus сигнал",
                "Некоторые конфликты в контексте",
            ]
        else:
            signal = SignalType.FLAT
            confidence = ConfidenceLevel.LOW
            reasoning = ["Слабый сигнал или много конфликтов"]

        # Определяем риск
        if context_conflicts > 2:
            risk_level = "Высокий"
        elif context_conflicts > 1:
            risk_level = "Средний"
        else:
            risk_level = "Низкий"

        # Условия входа и выхода
        entry_conditions = self._get_entry_conditions(
            signal, context_analysis, trigger_analysis
        )
        exit_conditions = self._get_exit_conditions(
            signal, context_analysis, trigger_analysis
        )

        return {
            "signal": signal,
            "confidence": confidence,
            "horizon": consensus_analysis.horizon,
            "reasoning": reasoning,
            "risk_level": risk_level,
            "entry_conditions": entry_conditions,
            "exit_conditions": exit_conditions,
        }

    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Определение уровня уверенности"""
        if score >= self.CONFIDENCE_THRESHOLDS[ConfidenceLevel.HIGH]:
            return ConfidenceLevel.HIGH
        if score >= self.CONFIDENCE_THRESHOLDS[ConfidenceLevel.MEDIUM]:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def _get_context_description(
        self, timeframe: str, score: float, valid: bool, regime: str | None
    ) -> str:
        """Описание контекстного анализа"""
        direction = "бычий" if score > 0 else "медвежий"
        strength = (
            "сильный"
            if abs(score) > 0.6
            else "умеренный"
            if abs(score) > 0.3
            else "слабый"
        )

        desc = f"{timeframe}: {strength} {direction} тренд"

        if regime:
            desc += f" ({self.REGIME_DESCRIPTIONS.get(regime, regime)})"

        if not valid:
            desc += " - НЕ ВАЛИДЕН"

        return desc

    def _get_trigger_description(
        self,
        timeframe: str,
        p_up: float,
        p_down: float,
        accel: int | None,
        micro_ok: bool | None,
    ) -> str:
        """Описание триггерного анализа"""
        if p_up > p_down:
            direction = "бычий"
            prob = p_up
        else:
            direction = "медвежий"
            prob = p_down

        desc = f"{timeframe}: {direction} сигнал ({prob:.1%})"

        if accel is not None:
            desc += f", {self.ACCEL_DESCRIPTIONS.get(accel, 'неизвестное ускорение')}"

        if micro_ok is not None:
            desc += f", микро-фильтр: {'OK' if micro_ok else 'FAIL'}"

        return desc

    def _get_consensus_description(
        self, horizon: str, side: SignalType, score: float
    ) -> str:
        """Описание consensus анализа"""
        signal_type = (
            "LONG"
            if side == SignalType.LONG
            else "SHORT"
            if side == SignalType.SHORT
            else "FLAT"
        )
        strength = (
            "сильный" if score > 0.7 else "умеренный" if score > 0.5 else "слабый"
        )

        return f"{horizon}: {strength} {signal_type} сигнал (score: {score:.2f})"

    def _get_entry_conditions(
        self,
        signal: SignalType,
        context_analysis: list[TimeframeAnalysis],
        trigger_analysis: list[TriggerAnalysis],
    ) -> list[str]:
        """Условия для входа в позицию"""
        conditions = []

        if signal == SignalType.LONG:
            conditions.append("Цена выше EMA21 на старших таймфреймах")
            conditions.append("RSI не в зоне перекупленности")
            conditions.append("MACD показывает положительную динамику")
        elif signal == SignalType.SHORT:
            conditions.append("Цена ниже EMA21 на старших таймфреймах")
            conditions.append("RSI не в зоне перепроданности")
            conditions.append("MACD показывает отрицательную динамику")

        # Добавляем специфичные условия
        for trigger in trigger_analysis:
            if trigger.timeframe == "5m" and trigger.accel == 1:
                conditions.append("Положительное ускорение на 5m")
            elif trigger.timeframe == "1m" and trigger.micro_ok:
                conditions.append("Прошел микро-фильтр ликвидности")

        return conditions

    def _get_exit_conditions(
        self,
        signal: SignalType,
        context_analysis: list[TimeframeAnalysis],
        trigger_analysis: list[TriggerAnalysis],
    ) -> list[str]:
        """Условия для выхода из позиции"""
        conditions = []

        if signal == SignalType.LONG:
            conditions.append("Цена пробила поддержку на 1D")
            conditions.append("RSI вошел в зону перекупленности")
            conditions.append("MACD показал разворот вниз")
        elif signal == SignalType.SHORT:
            conditions.append("Цена пробила сопротивление на 1D")
            conditions.append("RSI вошел в зону перепроданности")
            conditions.append("MACD показал разворот вверх")

        conditions.append("Изменение consensus сигнала")
        conditions.append("Достижение целевой прибыли")
        conditions.append("Достижение стоп-лосса")

        return conditions

    async def _get_context_data(self, session, symbol: str) -> list[dict]:
        """Получение контекстных данных"""
        query = text(
            """
            SELECT * FROM mtf.context
            WHERE symbol = :symbol
            ORDER BY timeframe, ts DESC
        """
        )

        result = await session.execute(query, {"symbol": symbol})
        return [dict(row) for row in result.fetchall()]

    async def _get_trigger_data(self, session, symbol: str) -> list[dict]:
        """Получение триггерных данных"""
        query = text(
            """
            SELECT * FROM mtf.triggers
            WHERE symbol = :symbol
            ORDER BY timeframe, ts DESC
        """
        )

        result = await session.execute(query, {"symbol": symbol})
        return [dict(row) for row in result.fetchall()]

    async def _get_consensus_data(self, session, symbol: str) -> list[dict]:
        """Получение consensus данных"""
        query = text(
            """
            SELECT * FROM mtf.consensus
            WHERE symbol = :symbol
            ORDER BY score DESC, ts DESC
        """
        )

        result = await session.execute(query, {"symbol": symbol})
        return [dict(row) for row in result.fetchall()]


# Глобальный экземпляр
decision_maker = MTFDecisionMaker()
