"""
Repository for data quality metrics.

Provides:
- Writing check results to ops.data_quality_metrics
- Reading latest metrics for dashboards
"""

from typing import Any, Protocol

from ..domain.quality import CheckResult


class MetricsPoolPort(Protocol):
    def acquire(self): ...


class QualityMetricsRepository:
    """Data quality metrics repository."""

    def __init__(self, pool: MetricsPoolPort) -> None:
        """Initialize with asyncpg connection pool."""
        self._pool = pool

    async def save_result(self, result: CheckResult) -> None:
        """Save a single check result."""
        await self.save_results([result])

    async def save_results(self, results: list[CheckResult]) -> None:
        """Save multiple check results."""
        if not results:
            return

        query = """
            INSERT INTO ops.data_quality_metrics
                (ts, check_name, severity, symbol, timeframe, value, meta)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        import json

        async with self._pool.acquire() as conn:
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
                        json.dumps(r.meta or {}),
                    )
                    for r in results
                ],
            )

    async def get_latest_by_check(
        self,
        check_name: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get latest metrics by check type."""
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
        """Get critical metrics from the last hour."""
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
        """Delete metrics older than N days. Returns count of deleted rows."""
        query = """
            DELETE FROM ops.data_quality_metrics
            WHERE ts < now() - ($1 || ' days')::interval
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(query, str(days))
            # result = "DELETE N"
            return int(result.split()[-1])
