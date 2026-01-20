"""
PromoteWorkflow - управление продвижением сигналов

Основные функции:
- Продвижение candidate → live
- Проверка DQ статуса
- Контроль лимитов
- Управление жизненным циклом сигналов
"""

import logging
from datetime import datetime
from typing import Any

from src.signals.database.client import SignalsDatabaseClient
from src.signals.models import (
    SignalCandidate,
    SignalConfig,
    SignalHistory,
    SignalLive,
    SignalStatus,
)
from src.signals.validation.validator import SignalValidator

logger = logging.getLogger(__name__)


class PromoteWorkflow:
    """
    Workflow для продвижения сигналов

    Управляет жизненным циклом сигналов:
    - Создание candidate из Decision
    - Валидация candidate
    - Продвижение candidate → live
    - Управление live сигналами
    - Архивирование в history
    """

    def __init__(
        self, config: SignalConfig, db_client: SignalsDatabaseClient | None = None
    ):
        self.config = config
        self.db_client = db_client
        self.validator = SignalValidator(config)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Кэш для отслеживания активных сигналов
        self._active_signals: dict[int, list[SignalLive]] = {}
        self._daily_signal_count: dict[str, int] = {}

    async def promote_candidate(
        self, candidate: SignalCandidate, force: bool = False
    ) -> SignalLive | None:
        """
        Продвижение кандидата в live сигнал

        Args:
            candidate: Кандидат для продвижения
            force: Принудительное продвижение (игнорирует некоторые проверки)

        Returns:
            SignalLive или None если продвижение не удалось
        """
        try:
            # 1. Проверяем DQ статус
            if not force and not await self._check_dq_status():
                self.logger.warning("DQ status check failed - promotion blocked")
                return None

            # 2. Проверяем лимиты риска
            if not force and not await self._check_risk_limits(candidate):
                self.logger.warning("Risk limits check failed - promotion blocked")
                return None

            # 3. Проверяем рыночные условия
            if not force and not await self._check_market_conditions(candidate):
                self.logger.warning(
                    "Market conditions check failed - promotion blocked"
                )
                return None

            # 4. Проверяем cooldown
            if not force and not await self._check_cooldown(candidate):
                self.logger.warning("Cooldown check failed - promotion blocked")
                return None

            # 5. Создаем live сигнал
            live_signal = SignalLive(
                candidate_id=candidate.id,
                decision=candidate.decision,
                status=SignalStatus.LIVE,
                activated_at=datetime.utcnow(),
            )

            # 6. Обновляем статус кандидата
            candidate.status = SignalStatus.VALIDATED

            # 7. Сохраняем в базу данных
            if self.db_client:
                await self.db_client.save_signal_live(live_signal)
                await self.db_client.update_signal_candidate(candidate)

            # 8. Обновляем кэш
            await self._update_cache(live_signal)

            self.logger.info(
                f"Successfully promoted candidate {candidate.id} to live signal {live_signal.id} "
                f"for symbol {candidate.decision.symbol_id}"
            )

            return live_signal

        except Exception as e:
            self.logger.error(f"Failed to promote candidate {candidate.id}: {e}")
            return None

    async def cancel_signal(
        self, live_signal: SignalLive, reason: str = "Manual cancellation"
    ) -> bool:
        """
        Отмена live сигнала

        Args:
            live_signal: Сигнал для отмены
            reason: Причина отмены

        Returns:
            True если отмена успешна
        """
        try:
            # Обновляем статус
            live_signal.status = SignalStatus.CANCELLED
            live_signal.execution_metrics["cancellation_reason"] = reason
            live_signal.execution_metrics["cancelled_at"] = datetime.utcnow()

            # Сохраняем в базу данных
            if self.db_client:
                await self.db_client.update_signal_live(live_signal)

            # Обновляем кэш
            await self._remove_from_cache(live_signal)

            self.logger.info(f"Cancelled signal {live_signal.id}: {reason}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cancel signal {live_signal.id}: {e}")
            return False

    async def expire_signal(self, live_signal: SignalLive) -> bool:
        """
        Истечение live сигнала по времени

        Args:
            live_signal: Сигнал для истечения

        Returns:
            True если истечение успешно
        """
        try:
            # Проверяем, действительно ли истек
            if live_signal.expires_at and datetime.utcnow() < live_signal.expires_at:
                return False

            # Обновляем статус
            live_signal.status = SignalStatus.EXPIRED
            live_signal.execution_metrics["expired_at"] = datetime.utcnow()

            # Создаем запись в истории
            history_record = SignalHistory(
                live_id=live_signal.id,
                decision=live_signal.decision,
                status=live_signal.status,
                activated_at=live_signal.activated_at,
                expires_at=live_signal.expires_at or datetime.utcnow(),
                executed_at=datetime.utcnow(),
                actual_r=0.0,  # Нет исполнения
                execution_metrics=live_signal.execution_metrics,
            )

            # Сохраняем в базу данных
            if self.db_client:
                await self.db_client.update_signal_live(live_signal)
                await self.db_client.save_signal_history(history_record)

            # Обновляем кэш
            await self._remove_from_cache(live_signal)

            self.logger.info(f"Expired signal {live_signal.id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to expire signal {live_signal.id}: {e}")
            return False

    async def execute_signal(
        self,
        live_signal: SignalLive,
        actual_r: float,
        execution_metrics: dict[str, Any],
    ) -> bool:
        """
        Исполнение live сигнала

        Args:
            live_signal: Сигнал для исполнения
            actual_r: Фактическая доходность
            execution_metrics: Метрики исполнения

        Returns:
            True если исполнение успешно
        """
        try:
            # Обновляем статус
            live_signal.status = SignalStatus.EXECUTED
            live_signal.executed_at = datetime.utcnow()
            live_signal.execution_metrics.update(execution_metrics)

            # Создаем запись в истории
            history_record = SignalHistory(
                live_id=live_signal.id,
                decision=live_signal.decision,
                status=live_signal.status,
                activated_at=live_signal.activated_at,
                expires_at=live_signal.expires_at or datetime.utcnow(),
                executed_at=live_signal.executed_at,
                actual_r=actual_r,
                execution_metrics=live_signal.execution_metrics,
                performance_metrics={
                    "expected_r": live_signal.decision.expected_r,
                    "actual_r": actual_r,
                    "r_difference": actual_r - live_signal.decision.expected_r,
                    "confidence": live_signal.decision.confidence,
                },
            )

            # Сохраняем в базу данных
            if self.db_client:
                await self.db_client.update_signal_live(live_signal)
                await self.db_client.save_signal_history(history_record)

            # Обновляем кэш
            await self._remove_from_cache(live_signal)

            self.logger.info(
                f"Executed signal {live_signal.id} with actual_r={actual_r:.3f}, "
                f"expected_r={live_signal.decision.expected_r:.3f}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to execute signal {live_signal.id}: {e}")
            return False

    async def cleanup_expired_signals(self) -> int:
        """
        Очистка истекших сигналов

        Returns:
            Количество очищенных сигналов
        """
        cleaned_count = 0

        try:
            # Получаем все активные сигналы
            active_signals = await self._get_active_signals()

            for signal in active_signals:
                if signal.expires_at and datetime.utcnow() >= signal.expires_at:
                    if await self.expire_signal(signal):
                        cleaned_count += 1

            self.logger.info(f"Cleaned up {cleaned_count} expired signals")
            return cleaned_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup expired signals: {e}")
            return 0

    async def _check_dq_status(self) -> bool:
        """Проверка статуса качества данных"""
        # Здесь должна быть интеграция с системой мониторинга DQ
        # Пока возвращаем True для простоты
        return True

    async def _check_risk_limits(self, candidate: SignalCandidate) -> bool:
        """Проверка лимитов риска"""

        # Проверяем максимальное количество одновременных сигналов
        active_count = await self._get_active_signals_count()
        if active_count >= self.config.max_concurrent_signals:
            self.logger.warning(
                f"Active signals count {active_count} >= max {self.config.max_concurrent_signals}"
            )
            return False

        # Проверяем дневной лимит сигналов
        today = datetime.utcnow().strftime("%Y-%m-%d")
        daily_count = self._daily_signal_count.get(today, 0)
        if daily_count >= self.config.max_daily_signals:
            self.logger.warning(
                f"Daily signals count {daily_count} >= max {self.config.max_daily_signals}"
            )
            return False

        return True

    async def _check_market_conditions(self, candidate: SignalCandidate) -> bool:
        """Проверка рыночных условий"""
        # Здесь должна быть интеграция с market_meta
        # Пока возвращаем True для простоты
        return True

    async def _check_cooldown(self, candidate: SignalCandidate) -> bool:
        """Проверка cooldown между сигналами"""

        symbol_id = candidate.decision.symbol_id

        # Получаем последний сигнал для этого символа
        last_signal = await self._get_last_signal_for_symbol(symbol_id)
        if not last_signal:
            return True

        # Проверяем cooldown
        time_since_last = (datetime.utcnow() - last_signal.activated_at).total_seconds()
        if time_since_last < self.config.cooldown_sec:
            self.logger.warning(
                f"Cooldown not met for symbol {symbol_id}: "
                f"{time_since_last:.0f}s < {self.config.cooldown_sec}s"
            )
            return False

        return True

    async def _update_cache(self, live_signal: SignalLive):
        """Обновление кэша активных сигналов"""
        symbol_id = live_signal.decision.symbol_id

        if symbol_id not in self._active_signals:
            self._active_signals[symbol_id] = []

        self._active_signals[symbol_id].append(live_signal)

        # Обновляем дневной счетчик
        today = datetime.utcnow().strftime("%Y-%m-%d")
        self._daily_signal_count[today] = self._daily_signal_count.get(today, 0) + 1

    async def _remove_from_cache(self, live_signal: SignalLive):
        """Удаление из кэша активных сигналов"""
        symbol_id = live_signal.decision.symbol_id

        if symbol_id in self._active_signals:
            self._active_signals[symbol_id] = [
                s for s in self._active_signals[symbol_id] if s.id != live_signal.id
            ]

            if not self._active_signals[symbol_id]:
                del self._active_signals[symbol_id]

    async def _get_active_signals(self) -> list[SignalLive]:
        """Получение всех активных сигналов"""
        all_signals = []
        for signals in self._active_signals.values():
            all_signals.extend(signals)
        return all_signals

    async def _get_active_signals_count(self) -> int:
        """Получение количества активных сигналов"""
        return sum(len(signals) for signals in self._active_signals.values())

    async def _get_last_signal_for_symbol(self, symbol_id: int) -> SignalLive | None:
        """Получение последнего сигнала для символа"""
        if symbol_id not in self._active_signals:
            return None

        signals = self._active_signals[symbol_id]
        if not signals:
            return None

        return max(signals, key=lambda s: s.activated_at)
