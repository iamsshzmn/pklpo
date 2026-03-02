"""
SignalsDatabaseClient - клиент для работы с базой данных signals

Основные функции:
- CRUD операции для candidates, live, history
- Получение метрик и статистики
- Управление жизненным циклом сигналов
"""

import json
import logging
from datetime import datetime
from uuid import UUID

import asyncpg

from src.signals.models import (
    SignalCandidate,
    SignalHistory,
    SignalLive,
    SignalMetrics,
    SignalStatus,
)

logger = logging.getLogger(__name__)


class SignalsDatabaseClient:
    """
    Асинхронный клиент для работы с базой данных signals

    Предоставляет методы для:
    - Сохранения и получения сигналов
    - Управления жизненным циклом
    - Получения метрик и статистики
    """

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._connection_pool: asyncpg.Pool | None = None

    async def initialize(self) -> bool:
        """Инициализация клиента и создание пула соединений"""
        try:
            self._connection_pool = await asyncpg.create_pool(
                self.database_url, min_size=1, max_size=10, command_timeout=60
            )

            # Проверяем соединение
            async with self._connection_pool.acquire() as conn:
                await conn.execute("SELECT 1")

            self.logger.info("SignalsDatabaseClient initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize SignalsDatabaseClient: {e}")
            return False

    async def close(self):
        """Закрытие пула соединений"""
        if self._connection_pool:
            await self._connection_pool.close()
            self.logger.info("SignalsDatabaseClient closed")

    # CRUD операции для candidates

    async def save_signal_candidate(self, candidate: SignalCandidate) -> bool:
        """Сохранение кандидата на сигнал"""
        try:
            async with self._connection_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO signals.candidates (
                        id, symbol_id, ts, horizon, side, entry, stop, take,
                        ttl_sec, confidence, expected_r, rationale, algo_version,
                        params_hash, run_id, status, created_at, validation_results
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18
                    )
                """,
                    candidate.id,
                    candidate.decision.symbol_id,
                    candidate.decision.ts,
                    candidate.decision.horizon.value,
                    candidate.decision.side.value,
                    candidate.decision.entry,
                    candidate.decision.stop,
                    candidate.decision.take,
                    candidate.decision.ttl_sec,
                    candidate.decision.confidence,
                    candidate.decision.expected_r,
                    candidate.decision.rationale,
                    candidate.decision.algo_version,
                    candidate.decision.params_hash,
                    candidate.decision.run_id,
                    candidate.status.value,
                    candidate.created_at,
                    (
                        json.dumps(candidate.validation_results.__dict__)
                        if candidate.validation_results
                        else None
                    ),
                )

            self.logger.debug(f"Saved signal candidate {candidate.id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save signal candidate {candidate.id}: {e}")
            return False

    async def get_signal_candidate(self, candidate_id: UUID) -> SignalCandidate | None:
        """Получение кандидата по ID"""
        try:
            async with self._connection_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM signals.candidates WHERE id = $1
                """,
                    candidate_id,
                )

                if not row:
                    return None

                return self._row_to_candidate(row)

        except Exception as e:
            self.logger.error(f"Failed to get signal candidate {candidate_id}: {e}")
            return None

    async def update_signal_candidate(self, candidate: SignalCandidate) -> bool:
        """Обновление кандидата"""
        try:
            async with self._connection_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE signals.candidates SET
                        status = $2,
                        validated_at = $3,
                        validation_results = $4
                    WHERE id = $1
                """,
                    candidate.id,
                    candidate.status.value,
                    (
                        candidate.validation_results.validated_at
                        if candidate.validation_results
                        else None
                    ),
                    (
                        json.dumps(candidate.validation_results.__dict__)
                        if candidate.validation_results
                        else None
                    ),
                )

            self.logger.debug(f"Updated signal candidate {candidate.id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update signal candidate {candidate.id}: {e}")
            return False

    async def list_signal_candidates(
        self,
        symbol_id: int | None = None,
        status: SignalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SignalCandidate]:
        """Получение списка кандидатов"""
        try:
            query = "SELECT * FROM signals.candidates WHERE 1=1"
            params = []
            param_count = 0

            if symbol_id is not None:
                param_count += 1
                query += f" AND symbol_id = ${param_count}"
                params.append(symbol_id)

            if status is not None:
                param_count += 1
                query += f" AND status = ${param_count}"
                params.append(status.value)

            query += f" ORDER BY created_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
            params.extend([limit, offset])

            async with self._connection_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

                return [self._row_to_candidate(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Failed to list signal candidates: {e}")
            return []

    # CRUD операции для live

    async def save_signal_live(self, live_signal: SignalLive) -> bool:
        """Сохранение live сигнала"""
        try:
            async with self._connection_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO signals.live (
                        id, candidate_id, symbol_id, ts, horizon, side, entry, stop, take,
                        ttl_sec, confidence, expected_r, rationale, algo_version,
                        params_hash, run_id, status, activated_at, expires_at, execution_metrics
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
                    )
                """,
                    live_signal.id,
                    live_signal.candidate_id,
                    live_signal.decision.symbol_id,
                    live_signal.decision.ts,
                    live_signal.decision.horizon.value,
                    live_signal.decision.side.value,
                    live_signal.decision.entry,
                    live_signal.decision.stop,
                    live_signal.decision.take,
                    live_signal.decision.ttl_sec,
                    live_signal.decision.confidence,
                    live_signal.decision.expected_r,
                    live_signal.decision.rationale,
                    live_signal.decision.algo_version,
                    live_signal.decision.params_hash,
                    live_signal.decision.run_id,
                    live_signal.status.value,
                    live_signal.activated_at,
                    live_signal.expires_at,
                    json.dumps(live_signal.execution_metrics),
                )

            self.logger.debug(f"Saved signal live {live_signal.id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save signal live {live_signal.id}: {e}")
            return False

    async def get_signal_live(self, live_id: UUID) -> SignalLive | None:
        """Получение live сигнала по ID"""
        try:
            async with self._connection_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM signals.live WHERE id = $1
                """,
                    live_id,
                )

                if not row:
                    return None

                return self._row_to_live(row)

        except Exception as e:
            self.logger.error(f"Failed to get signal live {live_id}: {e}")
            return None

    async def update_signal_live(self, live_signal: SignalLive) -> bool:
        """Обновление live сигнала"""
        try:
            async with self._connection_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE signals.live SET
                        status = $2,
                        executed_at = $3,
                        execution_metrics = $4
                    WHERE id = $1
                """,
                    live_signal.id,
                    live_signal.status.value,
                    live_signal.executed_at,
                    json.dumps(live_signal.execution_metrics),
                )

            self.logger.debug(f"Updated signal live {live_signal.id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update signal live {live_signal.id}: {e}")
            return False

    async def list_signal_live(
        self,
        symbol_id: int | None = None,
        status: SignalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SignalLive]:
        """Получение списка live сигналов"""
        try:
            query = "SELECT * FROM signals.live WHERE 1=1"
            params = []
            param_count = 0

            if symbol_id is not None:
                param_count += 1
                query += f" AND symbol_id = ${param_count}"
                params.append(symbol_id)

            if status is not None:
                param_count += 1
                query += f" AND status = ${param_count}"
                params.append(status.value)

            query += f" ORDER BY activated_at DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
            params.extend([limit, offset])

            async with self._connection_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

                return [self._row_to_live(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Failed to list signal live: {e}")
            return []

    # CRUD операции для history

    async def save_signal_history(self, history_record: SignalHistory) -> bool:
        """Сохранение записи истории"""
        try:
            async with self._connection_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO signals.history (
                        id, live_id, symbol_id, ts, horizon, side, entry, stop, take,
                        ttl_sec, confidence, expected_r, actual_r, rationale, algo_version,
                        params_hash, run_id, status, activated_at, expires_at, executed_at,
                        execution_metrics, performance_metrics
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                    )
                """,
                    history_record.id,
                    history_record.live_id,
                    history_record.decision.symbol_id,
                    history_record.decision.ts,
                    history_record.decision.horizon.value,
                    history_record.decision.side.value,
                    history_record.decision.entry,
                    history_record.decision.stop,
                    history_record.decision.take,
                    history_record.decision.ttl_sec,
                    history_record.decision.confidence,
                    history_record.decision.expected_r,
                    history_record.actual_r,
                    history_record.decision.rationale,
                    history_record.decision.algo_version,
                    history_record.decision.params_hash,
                    history_record.decision.run_id,
                    history_record.status.value,
                    history_record.activated_at,
                    history_record.expires_at,
                    history_record.executed_at,
                    json.dumps(history_record.execution_metrics),
                    json.dumps(history_record.performance_metrics),
                )

            self.logger.debug(f"Saved signal history {history_record.id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save signal history {history_record.id}: {e}")
            return False

    # Метрики и статистика

    async def get_signal_metrics(
        self,
        symbol_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> SignalMetrics:
        """Получение метрик сигналов"""
        try:
            query = """
                SELECT
                    COUNT(*) as total_generated,
                    COUNT(CASE WHEN status = 'validated' THEN 1 END) as total_validated,
                    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as total_rejected,
                    AVG(confidence) as avg_confidence,
                    AVG(expected_r) as avg_expected_r
                FROM signals.candidates
                WHERE 1=1
            """
            params = []
            param_count = 0

            if symbol_id is not None:
                param_count += 1
                query += f" AND symbol_id = ${param_count}"
                params.append(symbol_id)

            if date_from is not None:
                param_count += 1
                query += f" AND created_at >= ${param_count}"
                params.append(date_from)

            if date_to is not None:
                param_count += 1
                query += f" AND created_at <= ${param_count}"
                params.append(date_to)

            async with self._connection_pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)

                if not row:
                    return SignalMetrics()

                # Получаем метрики по live сигналам
                live_query = """
                    SELECT
                        COUNT(*) as total_promoted,
                        COUNT(CASE WHEN status = 'executed' THEN 1 END) as total_executed,
                        COUNT(CASE WHEN status = 'expired' THEN 1 END) as total_expired,
                        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as total_cancelled
                    FROM signals.live
                    WHERE 1=1
                """
                live_params = []
                live_param_count = 0

                if symbol_id is not None:
                    live_param_count += 1
                    live_query += f" AND symbol_id = ${live_param_count}"
                    live_params.append(symbol_id)

                if date_from is not None:
                    live_param_count += 1
                    live_query += f" AND activated_at >= ${live_param_count}"
                    live_params.append(date_from)

                if date_to is not None:
                    live_param_count += 1
                    live_query += f" AND activated_at <= ${live_param_count}"
                    live_params.append(date_to)

                live_row = await conn.fetchrow(live_query, *live_params)

                # Получаем метрики по истории
                history_query = """
                    SELECT
                        AVG(actual_r) as avg_actual_r,
                        AVG(EXTRACT(EPOCH FROM (executed_at - activated_at))) as avg_execution_time_sec
                    FROM signals.history
                    WHERE 1=1
                """
                history_params = []
                history_param_count = 0

                if symbol_id is not None:
                    history_param_count += 1
                    history_query += f" AND symbol_id = ${history_param_count}"
                    history_params.append(symbol_id)

                if date_from is not None:
                    history_param_count += 1
                    history_query += f" AND executed_at >= ${history_param_count}"
                    history_params.append(date_from)

                if date_to is not None:
                    history_param_count += 1
                    history_query += f" AND executed_at <= ${history_param_count}"
                    history_params.append(date_to)

                history_row = await conn.fetchrow(history_query, *history_params)

                # Собираем метрики
                return SignalMetrics(
                    total_generated=row["total_generated"] or 0,
                    total_validated=row["total_validated"] or 0,
                    total_promoted=live_row["total_promoted"] or 0 if live_row else 0,
                    total_executed=live_row["total_executed"] or 0 if live_row else 0,
                    total_failed=(
                        (live_row["total_expired"] or 0)
                        + (live_row["total_cancelled"] or 0)
                        if live_row
                        else 0
                    ),
                    validation_pass_rate=(
                        row["total_validated"] / max(row["total_generated"], 1)
                        if row["total_generated"]
                        else 0
                    ),
                    promotion_rate=(
                        (live_row["total_promoted"] or 0)
                        / max(row["total_validated"], 1)
                        if row["total_validated"]
                        else 0
                    ),
                    execution_success_rate=(
                        (live_row["total_executed"] or 0)
                        / max(live_row["total_promoted"], 1)
                        if live_row and live_row["total_promoted"]
                        else 0
                    ),
                    avg_expected_r=row["avg_expected_r"] or 0,
                    avg_actual_r=history_row["avg_actual_r"] or 0 if history_row else 0,
                    avg_confidence=row["avg_confidence"] or 0,
                    avg_execution_time_sec=(
                        history_row["avg_execution_time_sec"] or 0 if history_row else 0
                    ),
                )

        except Exception as e:
            self.logger.error(f"Failed to get signal metrics: {e}")
            return SignalMetrics()

    async def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Очистка старых данных"""
        try:
            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT signals.cleanup_old_data($1)", days_to_keep
                )

                self.logger.info(f"Cleaned up {result} old records")
                return result

        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
            return 0

    # Вспомогательные методы

    def _row_to_candidate(self, row) -> SignalCandidate:
        """Преобразование строки БД в SignalCandidate"""
        from src.signals.models import (
            Decision,
            SignalHorizon,
            SignalSide,
            ValidationResult,
        )

        decision = Decision(
            symbol_id=row["symbol_id"],
            ts=row["ts"],
            horizon=SignalHorizon(row["horizon"]),
            side=SignalSide(row["side"]),
            entry=float(row["entry"]),
            stop=float(row["stop"]),
            take=float(row["take"]),
            ttl_sec=row["ttl_sec"],
            confidence=float(row["confidence"]),
            expected_r=float(row["expected_r"]),
            rationale=row["rationale"],
            algo_version=row["algo_version"],
            params_hash=row["params_hash"],
            run_id=row["run_id"],
        )

        candidate = SignalCandidate(
            id=row["id"],
            decision=decision,
            status=SignalStatus(row["status"]),
            created_at=row["created_at"],
        )

        if row["validation_results"]:
            validation_data = json.loads(row["validation_results"])
            candidate.validation_results = ValidationResult(**validation_data)

        return candidate

    def _row_to_live(self, row) -> SignalLive:
        """Преобразование строки БД в SignalLive"""
        from src.signals.models import Decision, SignalHorizon, SignalSide

        decision = Decision(
            symbol_id=row["symbol_id"],
            ts=row["ts"],
            horizon=SignalHorizon(row["horizon"]),
            side=SignalSide(row["side"]),
            entry=float(row["entry"]),
            stop=float(row["stop"]),
            take=float(row["take"]),
            ttl_sec=row["ttl_sec"],
            confidence=float(row["confidence"]),
            expected_r=float(row["expected_r"]),
            rationale=row["rationale"],
            algo_version=row["algo_version"],
            params_hash=row["params_hash"],
            run_id=row["run_id"],
        )

        live_signal = SignalLive(
            id=row["id"],
            candidate_id=row["candidate_id"],
            decision=decision,
            status=SignalStatus(row["status"]),
            activated_at=row["activated_at"],
            expires_at=row["expires_at"],
            executed_at=row["executed_at"],
        )

        if row["execution_metrics"]:
            live_signal.execution_metrics = json.loads(row["execution_metrics"])

        return live_signal
