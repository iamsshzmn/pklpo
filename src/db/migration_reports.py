"""
Модуль для генерации отчётов о миграциях.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


class MigrationReport:
    """Класс для генерации отчётов о миграциях."""

    def __init__(self, migration_id: str, duration_ms: int):
        self.migration_id = migration_id
        self.duration_ms = duration_ms
        self.timestamp = datetime.now()
        self.report_data = {}

    async def generate_full_report(self) -> dict[str, Any]:
        """
        Генерирует полный отчёт о миграции.
        """
        logger.info(f"📊 Генерируем отчёт для миграции: {self.migration_id}")

        async with get_db_session() as session:
            # Базовая информация
            self.report_data = {
                "migration_id": self.migration_id,
                "duration_ms": self.duration_ms,
                "timestamp": self.timestamp.isoformat(),
                "duration_formatted": self._format_duration(self.duration_ms),
            }

            # Статистика базы данных
            await self._collect_database_stats(session)

            # Анализ изменений
            await self._analyze_changes(session)

            # Рекомендации
            await self._generate_recommendations(session)

            # Метрики производительности
            await self._collect_performance_metrics(session)

            logger.info("✅ Отчёт сгенерирован успешно")
            return self.report_data

    async def _collect_database_stats(self, session) -> None:
        """Собирает статистику базы данных."""
        try:
            # Общая статистика
            stats_q = text(
                """
                SELECT
                    COUNT(*) as total_tables,
                    SUM(pg_total_relation_size(schemaname||'.'||tablename)) as total_size_bytes,
                    SUM(pg_relation_size(schemaname||'.'||tablename)) as table_size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
            """
            )
            result = await session.execute(stats_q)
            stats = result.fetchone()

            # Статистика индексов
            index_q = text(
                """
                SELECT
                    COUNT(*) as total_indexes,
                    SUM(pg_relation_size(indexrelid)) as index_size_bytes
                FROM pg_indexes
                WHERE schemaname = 'public'
            """
            )
            result = await session.execute(index_q)
            index_stats = result.fetchone()

            # Статистика наших таблиц
            our_tables_q = text(
                """
                SELECT
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size_pretty,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
                    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.tablename) as column_count
                FROM pg_tables t
                WHERE schemaname = 'public'
                AND tablename IN ('ohlcv_p', 'indicators_p', 'instruments', 'schema_migrations')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """
            )
            result = await session.execute(our_tables_q)
            our_tables = result.fetchall()

            self.report_data["database_stats"] = {
                "total_tables": stats[0],
                "total_size_mb": round(stats[1] / 1024 / 1024, 2) if stats[1] else 0,
                "table_size_mb": round(stats[2] / 1024 / 1024, 2) if stats[2] else 0,
                "index_size_mb": (
                    round(index_stats[1] / 1024 / 1024, 2) if index_stats[1] else 0
                ),
                "total_indexes": index_stats[0],
                "our_tables": [
                    {
                        "name": row[0],
                        "size_pretty": row[1],
                        "size_mb": round(row[2] / 1024 / 1024, 2) if row[2] else 0,
                        "column_count": row[3],
                    }
                    for row in our_tables
                ],
            }

        except Exception as e:
            logger.error(f"❌ Ошибка при сборе статистики БД: {e}")
            self.report_data["database_stats"] = {"error": str(e)}

    async def _analyze_changes(self, session) -> None:
        """Анализирует изменения после миграции."""
        try:
            # Проверяем последние миграции
            recent_migrations_q = text(
                """
                SELECT
                    migration_id,
                    migration_name,
                    applied_at,
                    duration_ms,
                    status
                FROM schema_migrations
                ORDER BY applied_at DESC
                LIMIT 5
            """
            )
            result = await session.execute(recent_migrations_q)
            recent_migrations = result.fetchall()

            # Проверяем новые объекты
            new_objects_q = text(
                """
                SELECT
                    schemaname,
                    tablename,
                    tableowner,
                    tablespace
                FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename LIKE '%_p'  -- Партиционированные таблицы
                ORDER BY tablename
            """
            )
            result = await session.execute(new_objects_q)
            new_objects = result.fetchall()

            # Проверяем новые индексы
            new_indexes_q = text(
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND indexname LIKE '%_p%'  -- Индексы партиционированных таблиц
                ORDER BY tablename, indexname
            """
            )
            result = await session.execute(new_indexes_q)
            new_indexes = result.fetchall()

            self.report_data["changes_analysis"] = {
                "recent_migrations": [
                    {
                        "id": row[0],
                        "name": row[1],
                        "applied_at": row[2].isoformat() if row[2] else None,
                        "duration_ms": row[3],
                        "status": row[4],
                    }
                    for row in recent_migrations
                ],
                "new_partitioned_tables": [
                    {"name": row[1], "owner": row[2], "tablespace": row[3]}
                    for row in new_objects
                ],
                "new_indexes": [
                    {
                        "table": row[1],
                        "name": row[2],
                        "definition": (
                            row[3][:100] + "..." if len(row[3]) > 100 else row[3]
                        ),
                    }
                    for row in new_indexes
                ],
            }

        except Exception as e:
            logger.error(f"❌ Ошибка при анализе изменений: {e}")
            self.report_data["changes_analysis"] = {"error": str(e)}

    async def _generate_recommendations(self, session) -> None:
        """Генерирует рекомендации на основе анализа."""
        try:
            recommendations = []

            # Проверяем размер БД
            if (
                self.report_data.get("database_stats", {}).get("total_size_mb", 0)
                > 1000
            ):
                recommendations.append(
                    {
                        "type": "warning",
                        "message": "База данных превышает 1GB - рассмотрите архивирование старых данных",
                        "action": "DELETE FROM ohlcv WHERE timestamp < extract(epoch from now() - interval '6 months')",
                    }
                )

            # Проверяем фрагментацию индексов
            fragmentation_q = text(
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename IN ('ohlcv_p', 'indicators_p')
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 5
            """
            )
            result = await session.execute(fragmentation_q)
            large_indexes = result.fetchall()

            if large_indexes:
                recommendations.append(
                    {
                        "type": "info",
                        "message": f"Найдено {len(large_indexes)} крупных индексов - рассмотрите REINDEX",
                        "action": "REINDEX INDEX CONCURRENTLY index_name",
                    }
                )

            # Проверяем статистику
            stats_q = text(
                """
                SELECT
                    schemaname,
                    tablename,
                    last_analyze,
                    last_vacuum
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                AND tablename IN ('ohlcv_p', 'indicators_p')
            """
            )
            result = await session.execute(stats_q)
            table_stats = result.fetchall()

            for row in table_stats:
                if not row[2] or (datetime.now() - row[2]).days > 7:
                    recommendations.append(
                        {
                            "type": "warning",
                            "message": f"Статистика таблицы {row[1]} устарела",
                            "action": f"ANALYZE {row[1]}",
                        }
                    )

                if not row[3] or (datetime.now() - row[3]).days > 30:
                    recommendations.append(
                        {
                            "type": "info",
                            "message": f"Таблица {row[1]} не подвергалась VACUUM более 30 дней",
                            "action": f"VACUUM ANALYZE {row[1]}",
                        }
                    )

            # Общие рекомендации
            recommendations.extend(
                [
                    {
                        "type": "success",
                        "message": "Миграция выполнена успешно",
                        "action": "Продолжайте мониторинг производительности",
                    },
                    {
                        "type": "info",
                        "message": "Рекомендуется запустить тесты миграций",
                        "action": "python run_migration_tests.py",
                    },
                ]
            )

            self.report_data["recommendations"] = recommendations

        except Exception as e:
            logger.error(f"❌ Ошибка при генерации рекомендаций: {e}")
            self.report_data["recommendations"] = [{"type": "error", "message": str(e)}]

    async def _collect_performance_metrics(self, session) -> None:
        """Собирает метрики производительности."""
        try:
            # Время выполнения запросов
            performance_q = text(
                """
                SELECT
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows
                FROM pg_stat_statements
                WHERE query LIKE '%ohlcv_p%' OR query LIKE '%indicators_p%'
                ORDER BY total_time DESC
                LIMIT 10
            """
            )
            result = await session.execute(performance_q)
            slow_queries = result.fetchall()

            # Статистика блокировок
            locks_q = text(
                """
                SELECT
                    COUNT(*) as active_locks,
                    COUNT(CASE WHEN NOT granted THEN 1 END) as waiting_locks
                FROM pg_locks
                WHERE database = (SELECT oid FROM pg_database WHERE datname = current_database())
            """
            )
            result = await session.execute(locks_q)
            lock_stats = result.fetchone()

            # Размер логов
            log_q = text(
                """
                SELECT
                    pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) as wal_size
            """
            )
            result = await session.execute(log_q)
            wal_size = result.scalar()

            self.report_data["performance_metrics"] = {
                "slow_queries": [
                    {
                        "query": row[0][:100] + "..." if len(row[0]) > 100 else row[0],
                        "calls": row[1],
                        "total_time_ms": round(row[2], 2),
                        "mean_time_ms": round(row[3], 2),
                        "rows": row[4],
                    }
                    for row in slow_queries
                ],
                "lock_statistics": {
                    "active_locks": lock_stats[0],
                    "waiting_locks": lock_stats[1],
                },
                "wal_size": wal_size,
                "migration_performance": {
                    "duration_ms": self.duration_ms,
                    "performance_rating": self._rate_performance(),
                },
            }

        except Exception as e:
            logger.error(f"❌ Ошибка при сборе метрик производительности: {e}")
            self.report_data["performance_metrics"] = {"error": str(e)}

    def _format_duration(self, ms: int) -> str:
        """Форматирует длительность в читаемый вид."""
        if ms < 1000:
            return f"{ms}ms"
        if ms < 60000:
            return f"{ms/1000:.1f}s"
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.1f}s"

    def _rate_performance(self) -> str:
        """Оценивает производительность миграции."""
        if self.duration_ms < 1000:
            return "excellent"
        if self.duration_ms < 5000:
            return "good"
        if self.duration_ms < 30000:
            return "acceptable"
        return "slow"

    def save_report(self, filename: str | None = None) -> str:
        """Сохраняет отчёт в JSON файл."""
        if not filename:
            timestamp = self.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"migration_report_{self.migration_id}_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.report_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"📄 Отчёт сохранен в {filename}")
        return filename

    def print_summary(self) -> None:
        """Выводит краткое резюме отчёта."""
        print(f"\n📊 ОТЧЁТ О МИГРАЦИИ: {self.migration_id}")
        print("=" * 60)
        print(f"⏱️  Длительность: {self.report_data.get('duration_formatted', 'N/A')}")
        print(f"📅 Время выполнения: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        # Статистика БД
        db_stats = self.report_data.get("database_stats", {})
        if db_stats and "error" not in db_stats:
            print(f"🗄️  Размер БД: {db_stats.get('total_size_mb', 0)} MB")
            print(f"📋 Таблиц: {db_stats.get('total_tables', 0)}")
            print(f"🔍 Индексов: {db_stats.get('total_indexes', 0)}")

        # Рекомендации
        recommendations = self.report_data.get("recommendations", [])
        if recommendations:
            print(f"\n💡 Рекомендации ({len(recommendations)}):")
            for i, rec in enumerate(recommendations[:3], 1):  # Показываем первые 3
                print(f"  {i}. {rec['message']}")
            if len(recommendations) > 3:
                print(f"  ... и еще {len(recommendations) - 3} рекомендаций")

        # Производительность
        perf_metrics = self.report_data.get("performance_metrics", {})
        if perf_metrics and "error" not in perf_metrics:
            rating = perf_metrics.get("migration_performance", {}).get(
                "performance_rating", "unknown"
            )
            print(f"\n⚡ Оценка производительности: {rating.upper()}")

        print("=" * 60)


async def generate_migration_report(
    migration_id: str, duration_ms: int, save_file: bool = True
) -> MigrationReport:
    """
    Генерирует полный отчёт о миграции.

    Args:
        migration_id: ID миграции
        duration_ms: Длительность выполнения в миллисекундах
        save_file: Сохранять ли отчёт в файл

    Returns:
        MigrationReport: Объект отчёта
    """
    report = MigrationReport(migration_id, duration_ms)
    await report.generate_full_report()

    if save_file:
        filename = report.save_report()
        logger.info(f"📄 Отчёт сохранен: {filename}")

    return report


async def generate_system_health_report() -> dict[str, Any]:
    """
    Генерирует отчёт о состоянии системы.
    """
    logger.info("🏥 Генерируем отчёт о состоянии системы...")

    async with get_db_session() as session:
        try:
            # Общая статистика
            stats_q = text(
                """
                SELECT
                    COUNT(*) as total_tables,
                    SUM(pg_total_relation_size(schemaname||'.'||tablename)) as total_size_bytes,
                    COUNT(CASE WHEN tablename LIKE '%_p' THEN 1 END) as partitioned_tables
                FROM pg_tables
                WHERE schemaname = 'public'
            """
            )
            result = await session.execute(stats_q)
            stats = result.fetchone()

            # Статистика миграций
            migrations_q = text(
                """
                SELECT
                    COUNT(*) as total_migrations,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_migrations,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_migrations,
                    MAX(applied_at) as last_migration
                FROM schema_migrations
            """
            )
            result = await session.execute(migrations_q)
            migration_stats = result.fetchone()

            # Проверка здоровья
            health_checks = []

            # Проверка критичных таблиц
            critical_tables = [
                "ohlcv_p",
                "indicators_p",
                "instruments",
                "schema_migrations",
            ]
            for table in critical_tables:
                check_q = text("SELECT to_regclass(:table) IS NOT NULL")
                result = await session.execute(check_q, {"table": table})
                exists = result.scalar()
                health_checks.append(
                    {
                        "check": f"Table {table} exists",
                        "status": "✅" if exists else "❌",
                        "details": "Exists" if exists else "Missing",
                    }
                )

            # Проверка индексов
            index_q = text(
                "SELECT COUNT(*) FROM pg_indexes WHERE tablename IN ('ohlcv_p', 'indicators_p')"
            )
            result = await session.execute(index_q)
            index_count = result.scalar()
            health_checks.append(
                {
                    "check": "Indexes on partitioned tables",
                    "status": "✅" if index_count > 0 else "⚠️",
                    "details": f"{index_count} indexes found",
                }
            )

            # Проверка функций
            func_q = text(
                """
                SELECT COUNT(*) FROM pg_proc
                WHERE proname IN ('create_table_backup', 'check_migration_readiness')
            """
            )
            result = await session.execute(func_q)
            func_count = result.scalar()
            health_checks.append(
                {
                    "check": "Utility functions",
                    "status": "✅" if func_count >= 2 else "⚠️",
                    "details": f"{func_count}/2 functions found",
                }
            )

            return {
                "timestamp": datetime.now().isoformat(),
                "database_stats": {
                    "total_tables": stats[0],
                    "total_size_mb": (
                        round(stats[1] / 1024 / 1024, 2) if stats[1] else 0
                    ),
                    "partitioned_tables": stats[2],
                },
                "migration_stats": {
                    "total_migrations": migration_stats[0],
                    "successful_migrations": migration_stats[1],
                    "failed_migrations": migration_stats[2],
                    "last_migration": (
                        datetime.fromtimestamp(migration_stats[3]).isoformat()
                        if migration_stats[3]
                        else None
                    ),
                },
                "health_checks": health_checks,
                "overall_status": (
                    "healthy"
                    if all(check["status"] == "✅" for check in health_checks)
                    else "needs_attention"
                ),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка при генерации отчёта о состоянии: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    # Пример использования
    async def main():
        # Генерация отчёта о миграции
        report = await generate_migration_report("140_operational_reliability", 1500)
        report.print_summary()

        # Генерация отчёта о состоянии системы
        health_report = await generate_system_health_report()
        print(
            f"\n🏥 Состояние системы: {health_report.get('overall_status', 'unknown')}"
        )

    asyncio.run(main())
