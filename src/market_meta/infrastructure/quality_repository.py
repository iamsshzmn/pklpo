"""
Репозиторий для работы с метриками качества данных.

Предоставляет:
- Запись результатов проверок в ops.data_quality_metrics
- Чтение последних метрик для дашбордов
"""

from datetime import datetime
from typing import Any

from asyncpg import Connection, Pool

from ..domain.quality import CheckResult, Severity


class QualityMetricsRepository:
    """Репозиторий метрик качества данных."""

    def __init__(self, pool: Pool) -> None:
        """Инициализация с пулом соединений asyncpg."""
        self._pool = pool

    async def save_result(self, result: CheckResult) -> None:
        """Сохранить один результат проверки."""
        await self.save_results([result])

    async def save_results(self, results: list[CheckResult]) -> None:
        """Сохранить несколько результатов проверки."""
        if not results:
            return

        query = """
            INSERT INTO ops.data_quality_metrics
                (ts, check_name, severity, symbol, timeframe, value, meta)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        """
        async with self._pool.acquire() as conn:
            conn: Connection
            await conn.executemany(
                query,
                [
                    (
                        r.ts,
                        r.check_name,
                        str(r.severity),
                        r.symbol,
                        r.timeframe,
                        r.value,
                        r.meta,
                    )
                    for r in results
                ],
            )

    async def get_latest_by_check(
        self,
        check_name: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Получить последние метрики по типу проверки."""
        query = """
            SELECT ts, check_name, severity, symbol, timeframe, value, meta
            FROM ops.data_quality_metrics
            WHERE check_name = $1
            ORDER BY ts DESC
            LIMIT $2
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, check_name, limit)
            return [dict(r) for r in rows]

    async def get_critical_last_hour(self) -> list[dict[str, Any]]:
        """Получить критические метрики за последний час."""
        query = """
            SELECT ts, check_name, severity, symbol, timeframe, value, meta
            FROM ops.data_quality_metrics
            WHERE severity = 'critical'
              AND ts >= now() - interval '1 hour'
            ORDER BY ts DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(r) for r in rows]

    async def cleanup_old_metrics(self, days: int = 30) -> int:
        """Удалить метрики старше N дней. Возвращает количество удаленных."""
        query = """
            DELETE FROM ops.data_quality_metrics
            WHERE ts < now() - ($1 || ' days')::interval
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(query, str(days))
            # result = "DELETE N"
            return int(result.split()[-1])
