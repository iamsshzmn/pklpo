"""
DecisionMaker - преобразование MTF consensus в торговые решения

Основные функции:
- Анализ consensus результатов
- Расчет entry/stop/take уровней
- Определение confidence и expected_r
- Генерация rationale
"""

import logging

import pandas as pd

from src.mtf.consensus.models import ConsensusResult
from src.mtf.context.models import ContextResult
from src.mtf.triggers.models import TriggersResult
from src.signals.models import Decision, SignalConfig, SignalHorizon, SignalSide

logger = logging.getLogger(__name__)


class DecisionMaker:
    """
    Создатель торговых решений на основе MTF consensus

    Преобразует результаты MTF анализа в конкретные торговые решения
    с полным контрактом согласно task project.md
    """

    def __init__(self, config: SignalConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Параметры для расчета уровней
        self.atr_multiplier_stop = 2.0
        self.atr_multiplier_take = 3.0
        self.min_risk_reward_ratio = 1.5

        # Параметры для confidence
        self.consensus_weight = 0.4
        self.context_weight = 0.3
        self.triggers_weight = 0.3

    def create_decision(
        self,
        symbol_id: int,
        consensus_result: ConsensusResult,
        context_result: ContextResult,
        triggers_result: TriggersResult,
        current_price: float,
        atr: float,
        algo_version: str,
        params_hash: str,
        run_id: str,
    ) -> Decision | None:
        """
        Создание торгового решения на основе MTF результатов

        Args:
            symbol_id: ID символа
            consensus_result: Результат consensus анализа
            context_result: Результат context анализа
            triggers_result: Результат triggers анализа
            current_price: Текущая цена
            atr: Average True Range для расчета уровней
            algo_version: Версия алгоритма
            params_hash: Хеш параметров
            run_id: ID запуска

        Returns:
            Decision или None если сигнал не создается
        """
        try:
            # Определяем направление торговли
            side = self._determine_side(
                consensus_result, context_result, triggers_result
            )
            if side == SignalSide.FLAT:
                self.logger.debug(
                    f"No trading signal for symbol {symbol_id} - flat position"
                )
                return None

            # Определяем временной горизонт
            horizon = self._determine_horizon(consensus_result, context_result)

            # Рассчитываем уровни входа, стопа и тейка
            entry, stop, take = self._calculate_entry_stop_take(
                side, current_price, atr, consensus_result
            )

            # Рассчитываем confidence
            confidence = self._calculate_confidence(
                consensus_result, context_result, triggers_result
            )

            # Рассчитываем expected_r
            expected_r = self._calculate_expected_r(
                entry, stop, take, side, current_price
            )

            # Генерируем rationale
            rationale = self._generate_rationale(
                consensus_result, context_result, triggers_result, side, confidence
            )

            # Определяем TTL
            ttl_sec = self._calculate_ttl(horizon, consensus_result)

            # Создаем решение
            decision = Decision(
                symbol_id=symbol_id,
                ts=pd.Timestamp.now(),
                horizon=horizon,
                side=side,
                entry=entry,
                stop=stop,
                take=take,
                ttl_sec=ttl_sec,
                confidence=confidence,
                expected_r=expected_r,
                rationale=rationale,
                algo_version=algo_version,
                params_hash=params_hash,
                run_id=run_id,
            )

            self.logger.info(
                f"Created decision for symbol {symbol_id}: "
                f"side={side.value}, entry={entry:.4f}, stop={stop:.4f}, "
                f"take={take:.4f}, confidence={confidence:.3f}, expected_r={expected_r:.3f}"
            )

            return decision

        except Exception as e:
            self.logger.error(f"Failed to create decision for symbol {symbol_id}: {e}")
            return None

    def _determine_side(
        self,
        consensus_result: ConsensusResult,
        context_result: ContextResult,
        triggers_result: TriggersResult,
    ) -> SignalSide:
        """Определение направления торговли"""

        # Анализируем consensus
        consensus_side = None
        if consensus_result.side == "long":
            consensus_side = SignalSide.LONG
        elif consensus_result.side == "short":
            consensus_side = SignalSide.SHORT
        elif consensus_result.side == "flat":
            consensus_side = SignalSide.FLAT

        # Проверяем confidence consensus
        if consensus_result.confidence < 0.3:
            return SignalSide.FLAT

        # Анализируем triggers
        triggers_side = None
        if triggers_result.p_up > triggers_result.p_down + 0.1:
            triggers_side = SignalSide.LONG
        elif triggers_result.p_down > triggers_result.p_up + 0.1:
            triggers_side = SignalSide.SHORT

        # Анализируем context
        context_side = None
        if context_result.regime == "trend" and context_result.score > 0.1:
            context_side = SignalSide.LONG
        elif context_result.regime == "trend" and context_result.score < -0.1:
            context_side = SignalSide.SHORT

        # Принимаем решение на основе всех факторов
        if consensus_side == SignalSide.FLAT:
            return SignalSide.FLAT

        # Проверяем согласованность
        sides = [
            s for s in [consensus_side, triggers_side, context_side] if s is not None
        ]
        if not sides:
            return SignalSide.FLAT

        # Если большинство указывает на одно направление
        long_count = sum(1 for s in sides if s == SignalSide.LONG)
        short_count = sum(1 for s in sides if s == SignalSide.SHORT)

        if long_count > short_count:
            return SignalSide.LONG
        if short_count > long_count:
            return SignalSide.SHORT
        return SignalSide.FLAT

    def _determine_horizon(
        self, consensus_result: ConsensusResult, context_result: ContextResult
    ) -> SignalHorizon:
        """Определение временного горизонта"""

        # Анализируем consensus horizon
        if consensus_result.horizon == "intraday":
            return SignalHorizon.INTRADAY
        if consensus_result.horizon == "swing":
            return SignalHorizon.SWING
        if consensus_result.horizon == "week":
            return SignalHorizon.WEEK

        # Анализируем context regime
        if context_result.regime == "trend":
            return SignalHorizon.SWING
        if context_result.regime == "flat":
            return SignalHorizon.INTRADAY
        return SignalHorizon.INTRADAY

    def _calculate_entry_stop_take(
        self,
        side: SignalSide,
        current_price: float,
        atr: float,
        consensus_result: ConsensusResult,
    ) -> tuple[float, float, float]:
        """Расчет уровней входа, стопа и тейка"""

        # Базовые уровни на основе ATR
        stop_distance = atr * self.atr_multiplier_stop
        take_distance = atr * self.atr_multiplier_take

        if side == SignalSide.LONG:
            entry = current_price
            stop = entry - stop_distance
            take = entry + take_distance
        elif side == SignalSide.SHORT:
            entry = current_price
            stop = entry + stop_distance
            take = entry - take_distance
        else:
            raise ValueError(f"Invalid side for price calculation: {side}")

        # Корректируем на основе consensus confidence
        confidence_factor = consensus_result.confidence
        if confidence_factor > 0.8:
            # Высокая уверенность - более агрессивные уровни
            stop_distance *= 0.8
            take_distance *= 1.2
        elif confidence_factor < 0.5:
            # Низкая уверенность - более консервативные уровни
            stop_distance *= 1.2
            take_distance *= 0.8

        # Пересчитываем с учетом корректировки
        if side == SignalSide.LONG:
            stop = entry - stop_distance
            take = entry + take_distance
        else:
            stop = entry + stop_distance
            take = entry - take_distance

        # Проверяем минимальное соотношение риск/доходность
        risk = abs(entry - stop)
        reward = abs(take - entry)
        if reward / risk < self.min_risk_reward_ratio:
            # Увеличиваем take для достижения минимального соотношения
            if side == SignalSide.LONG:
                take = entry + risk * self.min_risk_reward_ratio
            else:
                take = entry - risk * self.min_risk_reward_ratio

        return entry, stop, take

    def _calculate_confidence(
        self,
        consensus_result: ConsensusResult,
        context_result: ContextResult,
        triggers_result: TriggersResult,
    ) -> float:
        """Расчет общей уверенности в сигнале"""

        # Базовые confidence от каждого модуля
        consensus_conf = consensus_result.confidence
        context_conf = min(abs(context_result.score) * 2, 1.0)  # Нормализуем score
        triggers_conf = max(triggers_result.p_up, triggers_result.p_down)

        # Взвешенная сумма
        total_confidence = (
            consensus_conf * self.consensus_weight
            + context_conf * self.context_weight
            + triggers_conf * self.triggers_weight
        )

        # Корректируем на основе coverage и disagreement
        if hasattr(consensus_result, "coverage"):
            coverage_factor = min(consensus_result.coverage, 1.0)
            total_confidence *= coverage_factor

        if hasattr(consensus_result, "disagreement"):
            disagreement_factor = max(0.5, 1.0 - consensus_result.disagreement)
            total_confidence *= disagreement_factor

        return min(max(total_confidence, 0.0), 1.0)

    def _calculate_expected_r(
        self,
        entry: float,
        stop: float,
        take: float,
        side: SignalSide,
        current_price: float,
    ) -> float:
        """Расчет ожидаемой доходности с учетом комиссий и проскальзывания"""

        # Базовая доходность
        risk = abs(entry - stop)
        reward = abs(take - entry)
        base_r = reward / risk

        # Учитываем комиссии (примерно 0.1% за сделку)
        fees_bps = 10  # 0.1%
        fees_factor = 1.0 - (fees_bps / 10000) * 2  # Комиссия за вход и выход

        # Учитываем проскальзывание (примерно 0.05%)
        slippage_bps = 5  # 0.05%
        slippage_factor = 1.0 - (slippage_bps / 10000)

        # Учитываем funding (примерно 0.01% в день)
        funding_bps = 1  # 0.01% в день
        funding_factor = 1.0 - (funding_bps / 10000)

        # Итоговая доходность
        return base_r * fees_factor * slippage_factor * funding_factor

    def _generate_rationale(
        self,
        consensus_result: ConsensusResult,
        context_result: ContextResult,
        triggers_result: TriggersResult,
        side: SignalSide,
        confidence: float,
    ) -> list[str]:
        """Генерация обоснования торгового решения"""

        rationale = []

        # Consensus rationale
        rationale.append(
            f"Consensus: {consensus_result.side} with confidence {consensus_result.confidence:.3f}"
        )
        if hasattr(consensus_result, "coverage"):
            rationale.append(f"Coverage: {consensus_result.coverage:.3f}")
        if hasattr(consensus_result, "disagreement"):
            rationale.append(f"Disagreement: {consensus_result.disagreement:.3f}")

        # Context rationale
        rationale.append(
            f"Market regime: {context_result.regime} (score: {context_result.score:.3f})"
        )
        if hasattr(context_result, "valid_reason_codes"):
            rationale.append(
                f"Valid reasons: {', '.join(context_result.valid_reason_codes)}"
            )

        # Triggers rationale
        rationale.append(
            f"Trigger probabilities: up={triggers_result.p_up:.3f}, down={triggers_result.p_down:.3f}"
        )
        if hasattr(triggers_result, "accel_vol_scaled"):
            rationale.append(f"Acceleration: {triggers_result.accel_vol_scaled:.3f}")
        if hasattr(triggers_result, "micro_ok"):
            rationale.append(f"Micro conditions: {triggers_result.micro_ok}")

        # Overall rationale
        rationale.append(f"Overall confidence: {confidence:.3f}")
        rationale.append(f"Trading side: {side.value}")

        return rationale

    def _calculate_ttl(
        self, horizon: SignalHorizon, consensus_result: ConsensusResult
    ) -> int:
        """Расчет времени жизни сигнала"""

        # Базовые TTL по горизонтам
        base_ttl = {
            SignalHorizon.INTRADAY: 3600,  # 1 час
            SignalHorizon.SWING: 86400,  # 24 часа
            SignalHorizon.WEEK: 604800,  # 7 дней
        }

        ttl = base_ttl.get(horizon, 3600)

        # Корректируем на основе confidence
        confidence_factor = consensus_result.confidence
        if confidence_factor > 0.8:
            ttl = int(ttl * 1.5)  # Увеличиваем для высокого confidence
        elif confidence_factor < 0.5:
            ttl = int(ttl * 0.5)  # Уменьшаем для низкого confidence

        # Ограничиваем максимальным TTL из конфигурации
        return min(ttl, self.config.max_ttl_sec)
