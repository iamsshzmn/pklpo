"""
Utilities for post-migration reports and system health snapshots.
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports") / "db"
TRACKED_TABLES = (
    "ohlcv_p",
    "indicators_p",
    "swap_ohlcv_p",
    "instruments",
    "schema_migrations",
    "migration_logs",
    "combination_features",
    "market_data_ext",
)


def _epoch_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).isoformat()
    return str(value)


def _shorten(text_value: str | None, limit: int = 120) -> str | None:
    if text_value is None or len(text_value) <= limit:
        return text_value
    return f"{text_value[:limit].rstrip()}..."


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class MigrationReport:
    """Collects structured information after a migration run."""

    def __init__(self, migration_id: str, duration_ms: int):
        self.migration_id = migration_id
        self.duration_ms = duration_ms
        self.timestamp = datetime.now()
        self.report_data: dict[str, Any] = {
            "migration_id": migration_id,
            "duration_ms": duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "duration_formatted": self._format_duration(duration_ms),
        }

    async def _run_section(self, section_name: str, collector) -> None:
        try:
            async with get_db_session() as session:
                self.report_data[section_name] = await collector(session)
        except SQLAlchemyError as exc:
            logger.warning("migration report section %s failed: %s", section_name, exc)
            self.report_data[section_name] = {"error": str(exc)}
        except Exception as exc:
            logger.warning("unexpected error in section %s: %s", section_name, exc)
            self.report_data[section_name] = {"error": str(exc)}

    async def generate_full_report(self) -> dict[str, Any]:
        logger.info("generating migration report for %s", self.migration_id)

        await self._run_section("database_stats", self._collect_database_stats)
        await self._run_section("changes_analysis", self._analyze_changes)
        await self._run_section("recommendations", self._generate_recommendations)
        await self._run_section(
            "performance_metrics",
            self._collect_performance_metrics,
        )

        logger.info("migration report generated for %s", self.migration_id)
        return self.report_data

    async def _collect_database_stats(self, session) -> dict[str, Any]:
        db_stats_q = text(
            """
            SELECT
                COUNT(*) AS total_tables,
                COALESCE(SUM(pg_total_relation_size(c.oid)), 0) AS total_size_bytes,
                COALESCE(SUM(pg_relation_size(c.oid)), 0) AS table_size_bytes
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind IN ('r', 'p', 'm')
            """
        )
        db_stats = (await session.execute(db_stats_q)).one()

        index_stats_q = text(
            """
            SELECT
                COUNT(*) AS total_indexes,
                COALESCE(SUM(pg_relation_size(i.indexrelid)), 0) AS index_size_bytes
            FROM pg_index i
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_namespace n ON n.oid = idx.relnamespace
            WHERE n.nspname = 'public'
            """
        )
        index_stats = (await session.execute(index_stats_q)).one()

        tracked_tables_q = text(
            """
            SELECT
                c.relname AS table_name,
                c.relkind AS relkind,
                pg_total_relation_size(c.oid) AS size_bytes,
                pg_size_pretty(pg_total_relation_size(c.oid)) AS size_pretty,
                COALESCE(cols.column_count, 0) AS column_count
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN (
                SELECT
                    table_name,
                    COUNT(*) AS column_count
                FROM information_schema.columns
                WHERE table_schema = 'public'
                GROUP BY table_name
            ) cols ON cols.table_name = c.relname
            WHERE n.nspname = 'public'
              AND c.relname = ANY(:tracked_tables)
              AND c.relkind IN ('r', 'p', 'm')
            ORDER BY size_bytes DESC, c.relname
            """
        )
        tracked_tables = (
            await session.execute(
                tracked_tables_q, {"tracked_tables": list(TRACKED_TABLES)}
            )
        ).fetchall()

        return {
            "total_tables": int(db_stats.total_tables or 0),
            "total_size_mb": round((db_stats.total_size_bytes or 0) / 1024 / 1024, 2),
            "table_size_mb": round((db_stats.table_size_bytes or 0) / 1024 / 1024, 2),
            "total_indexes": int(index_stats.total_indexes or 0),
            "index_size_mb": round(
                (index_stats.index_size_bytes or 0) / 1024 / 1024,
                2,
            ),
            "tracked_tables": [
                {
                    "name": row.table_name,
                    "kind": row.relkind,
                    "size_pretty": row.size_pretty,
                    "size_mb": round((row.size_bytes or 0) / 1024 / 1024, 2),
                    "column_count": int(row.column_count or 0),
                }
                for row in tracked_tables
            ],
        }

    async def _analyze_changes(self, session) -> dict[str, Any]:
        migrations_q = text(
            """
            SELECT
                id,
                name,
                applied_at,
                duration_ms,
                status,
                attempt,
                error
            FROM schema_migrations
            ORDER BY applied_at DESC
            LIMIT 5
            """
        )
        recent_migrations = (await session.execute(migrations_q)).fetchall()

        current_migration_q = text(
            """
            SELECT
                id,
                name,
                applied_at,
                duration_ms,
                status,
                attempt,
                error
            FROM schema_migrations
            WHERE id = :migration_id
            """
        )
        current_migration = (
            await session.execute(
                current_migration_q,
                {"migration_id": self.migration_id},
            )
        ).fetchone()

        partitioned_tables_q = text(
            """
            SELECT c.relname
            FROM pg_partitioned_table pt
            JOIN pg_class c ON c.oid = pt.partrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
            ORDER BY c.relname
            """
        )
        partitioned_tables = (await session.execute(partitioned_tables_q)).fetchall()

        materialized_views_q = text(
            """
            SELECT matviewname
            FROM pg_matviews
            WHERE schemaname = 'public'
            ORDER BY matviewname
            """
        )
        materialized_views = (await session.execute(materialized_views_q)).fetchall()

        migration_related_indexes_q = text(
            """
            SELECT
                tablename,
                indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND (
                    tablename = ANY(:tracked_tables)
                 OR indexname ILIKE :migration_hint
              )
            ORDER BY tablename, indexname
            LIMIT 20
            """
        )
        migration_related_indexes = (
            await session.execute(
                migration_related_indexes_q,
                {
                    "tracked_tables": list(TRACKED_TABLES),
                    "migration_hint": f"%{self.migration_id.split('_', 1)[-1]}%",
                },
            )
        ).fetchall()

        return {
            "current_migration": (
                {
                    "id": current_migration.id,
                    "name": current_migration.name,
                    "applied_at": _epoch_to_iso(current_migration.applied_at),
                    "duration_ms": current_migration.duration_ms,
                    "status": current_migration.status,
                    "attempt": current_migration.attempt,
                    "error": current_migration.error,
                }
                if current_migration
                else None
            ),
            "recent_migrations": [
                {
                    "id": row.id,
                    "name": row.name,
                    "applied_at": _epoch_to_iso(row.applied_at),
                    "duration_ms": row.duration_ms,
                    "status": row.status,
                    "attempt": row.attempt,
                    "error": row.error,
                }
                for row in recent_migrations
            ],
            "partitioned_tables": [row.relname for row in partitioned_tables],
            "materialized_views": [row.matviewname for row in materialized_views],
            "relevant_indexes": [
                {"table": row.tablename, "name": row.indexname}
                for row in migration_related_indexes
            ],
        }

    async def _generate_recommendations(self, session) -> list[dict[str, str]]:
        recommendations: list[dict[str, str]] = []

        db_stats = self.report_data.get("database_stats", {})
        if (
            isinstance(db_stats, dict)
            and "error" not in db_stats
            and db_stats.get("total_size_mb", 0) > 1024
        ):
            recommendations.append(
                {
                    "type": "warning",
                    "message": "Database size is above 1 GB. Review retention and archival policy.",
                    "action": "Inspect large tables and schedule cleanup for cold data.",
                }
            )

        stale_stats_q = text(
            """
            SELECT
                relname,
                last_analyze,
                last_vacuum
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
              AND relname = ANY(:tracked_tables)
            ORDER BY relname
            """
        )
        stale_stats = (
            await session.execute(
                stale_stats_q, {"tracked_tables": list(TRACKED_TABLES)}
            )
        ).fetchall()

        now = datetime.now()
        for row in stale_stats:
            last_analyze = (
                _normalize_datetime(row.last_analyze) if row.last_analyze else None
            )
            last_vacuum = (
                _normalize_datetime(row.last_vacuum) if row.last_vacuum else None
            )

            if last_analyze is None or (now - last_analyze).days > 7:
                recommendations.append(
                    {
                        "type": "warning",
                        "message": f"Statistics are stale for {row.relname}.",
                        "action": f"ANALYZE {row.relname};",
                    }
                )
            if last_vacuum is None or (now - last_vacuum).days > 30:
                recommendations.append(
                    {
                        "type": "info",
                        "message": f"Vacuum has not run recently for {row.relname}.",
                        "action": f"VACUUM ANALYZE {row.relname};",
                    }
                )

        if not recommendations:
            recommendations.append(
                {
                    "type": "success",
                    "message": "No immediate post-migration actions detected.",
                    "action": "Continue with normal monitoring.",
                }
            )

        return recommendations

    async def _collect_performance_metrics(self, session) -> dict[str, Any]:
        pg_stat_statements_q = text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_extension
                WHERE extname = 'pg_stat_statements'
            )
            """
        )
        has_pg_stat_statements = bool(
            (await session.execute(pg_stat_statements_q)).scalar()
        )

        slow_queries: list[dict[str, Any]] = []
        if has_pg_stat_statements:
            slow_queries_q = text(
                """
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    rows
                FROM pg_stat_statements
                WHERE query ILIKE '%ohlcv%'
                   OR query ILIKE '%indicator%'
                   OR query ILIKE '%schema_migrations%'
                ORDER BY total_exec_time DESC
                LIMIT 10
                """
            )
            try:
                slow_rows = (await session.execute(slow_queries_q)).fetchall()
            except SQLAlchemyError:
                fallback_q = text(
                    """
                    SELECT
                        query,
                        calls,
                        total_time,
                        mean_time,
                        rows
                    FROM pg_stat_statements
                    WHERE query ILIKE '%ohlcv%'
                       OR query ILIKE '%indicator%'
                       OR query ILIKE '%schema_migrations%'
                    ORDER BY total_time DESC
                    LIMIT 10
                    """
                )
                slow_rows = (await session.execute(fallback_q)).fetchall()

            slow_queries = [
                {
                    "query": _shorten(row[0]),
                    "calls": int(row[1] or 0),
                    "total_time_ms": round(float(row[2] or 0), 2),
                    "mean_time_ms": round(float(row[3] or 0), 2),
                    "rows": int(row[4] or 0),
                }
                for row in slow_rows
            ]

        locks_q = text(
            """
            SELECT
                COUNT(*) AS active_locks,
                COUNT(*) FILTER (WHERE NOT granted) AS waiting_locks
            FROM pg_locks
            WHERE database = (SELECT oid FROM pg_database WHERE datname = current_database())
            """
        )
        lock_stats = (await session.execute(locks_q)).one()

        wal_q = text(
            """
            SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) AS wal_size
            """
        )
        wal_size = (await session.execute(wal_q)).scalar()

        return {
            "pg_stat_statements_enabled": has_pg_stat_statements,
            "slow_queries": slow_queries,
            "lock_statistics": {
                "active_locks": int(lock_stats.active_locks or 0),
                "waiting_locks": int(lock_stats.waiting_locks or 0),
            },
            "wal_size": wal_size,
            "migration_performance": {
                "duration_ms": self.duration_ms,
                "performance_rating": self._rate_performance(),
            },
        }

    def _format_duration(self, ms: int) -> str:
        if ms < 1000:
            return f"{ms}ms"
        if ms < 60000:
            return f"{ms / 1000:.1f}s"
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.1f}s"

    def _rate_performance(self) -> str:
        if self.duration_ms < 1000:
            return "excellent"
        if self.duration_ms < 5000:
            return "good"
        if self.duration_ms < 30000:
            return "acceptable"
        return "slow"

    def save_report(self, filename: str | None = None) -> str:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        if not filename:
            timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
            path = (
                REPORTS_DIR / f"migration_report_{self.migration_id}_{timestamp}.json"
            )
        else:
            path = Path(filename)

        with path.open("w", encoding="utf-8") as file_handle:
            json.dump(
                self.report_data,
                file_handle,
                indent=2,
                ensure_ascii=False,
                default=_json_default,
            )

        logger.info("migration report saved to %s", path)
        return str(path)

    def print_summary(self) -> None:
        print(f"\nMigration report: {self.migration_id}")
        print("=" * 60)
        print(f"Duration: {self.report_data.get('duration_formatted', 'N/A')}")
        print(f"Generated at: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        db_stats = self.report_data.get("database_stats", {})
        if db_stats and "error" not in db_stats:
            print(f"Database size: {db_stats.get('total_size_mb', 0)} MB")
            print(f"Tables: {db_stats.get('total_tables', 0)}")
            print(f"Indexes: {db_stats.get('total_indexes', 0)}")

        recommendations = self.report_data.get("recommendations", [])
        if recommendations:
            print(f"\nRecommendations ({len(recommendations)}):")
            for index, recommendation in enumerate(recommendations[:3], start=1):
                print(f"  {index}. {recommendation['message']}")
            if len(recommendations) > 3:
                print(f"  ... and {len(recommendations) - 3} more")

        perf_metrics = self.report_data.get("performance_metrics", {})
        if perf_metrics and "error" not in perf_metrics:
            rating = perf_metrics.get("migration_performance", {}).get(
                "performance_rating",
                "unknown",
            )
            print(f"\nPerformance rating: {rating.upper()}")

        print("=" * 60)


async def generate_migration_report(
    migration_id: str,
    duration_ms: int,
    save_file: bool = True,
) -> MigrationReport:
    report = MigrationReport(migration_id, duration_ms)
    await report.generate_full_report()

    if save_file:
        report.save_report()

    return report


async def generate_system_health_report() -> dict[str, Any]:
    logger.info("generating system health report")

    try:
        async with get_db_session() as session:
            db_stats_q = text(
                """
                SELECT
                    COUNT(*) AS total_tables,
                    COALESCE(SUM(pg_total_relation_size(c.oid)), 0) AS total_size_bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p', 'm')
                """
            )
            db_stats = (await session.execute(db_stats_q)).one()

            partitioned_tables_q = text(
                """
                SELECT COUNT(*)
                FROM pg_partitioned_table pt
                JOIN pg_class c ON c.oid = pt.partrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                """
            )
            partitioned_tables = (await session.execute(partitioned_tables_q)).scalar()

            migrations_q = text(
                """
                SELECT
                    COUNT(*) AS total_migrations,
                    COUNT(*) FILTER (WHERE status = 'applied') AS applied_migrations,
                    COUNT(*) FILTER (WHERE status = 'failed') AS failed_migrations,
                    MAX(applied_at) AS last_migration
                FROM schema_migrations
                """
            )
            migration_stats = (await session.execute(migrations_q)).one()

            health_checks: list[dict[str, str]] = []

            for table_name in (
                "ohlcv_p",
                "indicators_p",
                "instruments",
                "schema_migrations",
            ):
                exists_q = text("SELECT to_regclass(:qualified_name) IS NOT NULL")
                exists = bool(
                    (
                        await session.execute(
                            exists_q,
                            {"qualified_name": f"public.{table_name}"},
                        )
                    ).scalar()
                )
                health_checks.append(
                    {
                        "check": f"table {table_name}",
                        "status": "ok" if exists else "error",
                        "details": "exists" if exists else "missing",
                    }
                )

            index_count_q = text(
                """
                SELECT COUNT(*)
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('ohlcv_p', 'indicators_p', 'swap_ohlcv_p')
                """
            )
            index_count = int((await session.execute(index_count_q)).scalar() or 0)
            health_checks.append(
                {
                    "check": "indexes on core tables",
                    "status": "ok" if index_count > 0 else "warning",
                    "details": f"{index_count} indexes found",
                }
            )

            failed_migrations_q = text(
                """
                SELECT id, error
                FROM schema_migrations
                WHERE status = 'failed'
                ORDER BY applied_at DESC
                LIMIT 3
                """
            )
            failed_migrations = (await session.execute(failed_migrations_q)).fetchall()
            if failed_migrations:
                health_checks.append(
                    {
                        "check": "recent failed migrations",
                        "status": "warning",
                        "details": ", ".join(row.id for row in failed_migrations),
                    }
                )

            overall_status = "healthy"
            if any(check["status"] == "error" for check in health_checks):
                overall_status = "needs_attention"
            elif any(check["status"] == "warning" for check in health_checks):
                overall_status = "degraded"

            return {
                "timestamp": datetime.now().isoformat(),
                "database_stats": {
                    "total_tables": int(db_stats.total_tables or 0),
                    "total_size_mb": round(
                        (db_stats.total_size_bytes or 0) / 1024 / 1024,
                        2,
                    ),
                    "partitioned_tables": int(partitioned_tables or 0),
                },
                "migration_stats": {
                    "total_migrations": int(migration_stats.total_migrations or 0),
                    "applied_migrations": int(migration_stats.applied_migrations or 0),
                    "failed_migrations": int(migration_stats.failed_migrations or 0),
                    "last_migration": _epoch_to_iso(migration_stats.last_migration),
                },
                "health_checks": health_checks,
                "overall_status": overall_status,
            }
    except Exception as exc:
        logger.error("failed to generate system health report: %s", exc)
        return {"error": str(exc)}


if __name__ == "__main__":

    async def main() -> None:
        report = await generate_migration_report("140_operational_reliability", 1500)
        report.print_summary()

        health_report = await generate_system_health_report()
        print(f"\nSystem health: {health_report.get('overall_status', 'unknown')}")

    asyncio.run(main())
