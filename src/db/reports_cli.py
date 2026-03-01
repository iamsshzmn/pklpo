#!/usr/bin/env python3
"""
CLI для работы с отчётами миграций.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.db.migration_reports import (
    generate_migration_report,
    generate_system_health_report,
)
from src.utils.session_utils import get_db_session


async def show_migration_status() -> None:
    """Показывает статус миграций."""
    from src.db.migration_runner import get_migrations

    async with get_db_session() as session:
        # Получаем список всех миграций
        migrations = get_migrations()

        # Получаем статус из БД
        status_q = text(
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
        """
        )
        result = await session.execute(status_q)
        applied_migrations = {row[0]: row for row in result.fetchall()}

        print("📋 СТАТУС МИГРАЦИЙ")
        print("=" * 80)
        print(
            f"{'ID':<20} {'Статус':<10} {'Длительность':<12} {'Попыток':<8} {'Последнее применение'}"
        )
        print("-" * 80)

        for migration in migrations:
            migration_id = migration.id
            if migration_id in applied_migrations:
                row = applied_migrations[migration_id]
                status = row[4]
                duration = f"{row[3]}ms" if row[3] else "N/A"
                attempts = row[5] if row[5] else 1
                applied_at = row[2]
                if applied_at:
                    # applied_at хранится как int timestamp
                    from datetime import datetime

                    applied_str = datetime.fromtimestamp(applied_at).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                else:
                    applied_str = "N/A"

                status_icon = {"applied": "✅", "failed": "❌", "planned": "📝"}.get(
                    status, "❓"
                )

                print(
                    f"{migration_id:<20} {status_icon} {status:<8} {duration:<12} {attempts:<8} {applied_str}"
                )
            else:
                print(f"{migration_id:<20} ⏳ pending    N/A         N/A      N/A")

        print("-" * 80)

        # Статистика
        total = len(migrations)
        applied = len([m for m in applied_migrations.values() if m[4] == "applied"])
        failed = len([m for m in applied_migrations.values() if m[4] == "failed"])

        print(f"📊 Всего миграций: {total}, Применено: {applied}, Ошибок: {failed}")


async def show_system_health() -> None:
    """Показывает состояние системы."""
    health_report = await generate_system_health_report()

    if "error" in health_report:
        print(f"❌ Ошибка при получении отчёта: {health_report['error']}")
        return

    print("🏥 СОСТОЯНИЕ СИСТЕМЫ")
    print("=" * 50)

    # Базовая статистика
    db_stats = health_report.get("database_stats", {})
    print("🗄️  База данных:")
    print(f"   • Таблиц: {db_stats.get('total_tables', 0)}")
    print(f"   • Размер: {db_stats.get('total_size_mb', 0)} MB")
    print(f"   • Партиционированных таблиц: {db_stats.get('partitioned_tables', 0)}")

    # Статистика миграций
    migration_stats = health_report.get("migration_stats", {})
    print("\n📦 Миграции:")
    print(f"   • Всего: {migration_stats.get('total_migrations', 0)}")
    print(f"   • Успешных: {migration_stats.get('successful_migrations', 0)}")
    print(f"   • Ошибок: {migration_stats.get('failed_migrations', 0)}")

    last_migration = migration_stats.get("last_migration")
    if last_migration:
        print(f"   • Последняя: {last_migration}")

    # Проверки здоровья
    health_checks = health_report.get("health_checks", [])
    print("\n🔍 Проверки здоровья:")
    for check in health_checks:
        status = check["status"]
        message = check["check"]
        details = check.get("details", "")
        print(f"   {status} {message}: {details}")

    # Общий статус
    overall_status = health_report.get("overall_status", "unknown")
    status_icon = "✅" if overall_status == "healthy" else "⚠️"
    print(f"\n{status_icon} Общий статус: {overall_status.upper()}")


async def generate_report_for_migration(
    migration_id: str, duration_ms: int | None = None
) -> None:
    """Генерирует отчёт для конкретной миграции."""
    if duration_ms is None:
        # Получаем длительность из БД
        async with get_db_session() as session:
            duration_q = text(
                "SELECT duration_ms FROM schema_migrations WHERE id = :id"
            )
            result = await session.execute(duration_q, {"id": migration_id})
            duration_result = result.scalar()

            if duration_result is None:
                print(f"❌ Миграция {migration_id} не найдена в БД")
                return

            duration_ms = duration_result

    try:
        report = await generate_migration_report(
            migration_id, duration_ms, save_file=True
        )
        report.print_summary()
    except Exception as e:
        print(f"❌ Ошибка при генерации отчёта: {e}")


async def show_database_stats() -> None:
    """Показывает детальную статистику базы данных."""
    async with get_db_session() as session:
        # Размеры таблиц
        size_q = text(
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
        result = await session.execute(size_q)
        tables = result.fetchall()

        print("📊 СТАТИСТИКА НАШИХ ТАБЛИЦ")
        print("=" * 60)
        print(f"{'Таблица':<20} {'Размер':<12} {'Колонок':<8} {'Размер (MB)'}")
        print("-" * 60)

        for table in tables:
            name = table[0]
            size_pretty = table[1]
            size_bytes = table[2] or 0
            column_count = table[3]
            size_mb = round(size_bytes / 1024 / 1024, 2)

            print(f"{name:<20} {size_pretty:<12} {column_count:<8} {size_mb}")

        print("-" * 60)

        # Статистика индексов
        index_q = text(
            """
            SELECT
                tablename,
                COUNT(*) as index_count,
                'N/A' as total_index_size
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename IN ('ohlcv_p', 'indicators_p', 'instruments')
            GROUP BY tablename
            ORDER BY tablename
        """
        )
        result = await session.execute(index_q)
        indexes = result.fetchall()

        print("\n🔍 СТАТИСТИКА ИНДЕКСОВ")
        print("=" * 40)
        print(f"{'Таблица':<20} {'Индексов':<10} {'Общий размер'}")
        print("-" * 40)

        for index in indexes:
            table = index[0]
            count = index[1]
            size = index[2]
            print(f"{table:<20} {count:<10} {size}")

        print("-" * 40)


async def show_performance_metrics() -> None:
    """Показывает метрики производительности."""
    async with get_db_session() as session:
        # Проверяем доступность pg_stat_statements
        check_ext_q = text(
            """
            SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
        """
        )
        try:
            result = await session.execute(check_ext_q)
            has_pg_stat_statements = result.scalar() is not None
        except Exception:
            has_pg_stat_statements = False

        if has_pg_stat_statements:
            # Медленные запросы
            slow_q = text(
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
            result = await session.execute(slow_q)
            slow_queries = result.fetchall()

            print("⚡ МЕДЛЕННЫЕ ЗАПРОСЫ")
            print("=" * 80)
            print(
                f"{'Запрос':<50} {'Вызовов':<8} {'Общее время':<12} {'Среднее время':<12} {'Строк'}"
            )
            print("-" * 80)

            for query in slow_queries:
                query_text = query[0][:47] + "..." if len(query[0]) > 50 else query[0]
                calls = query[1]
                total_time = round(query[2], 2)
                mean_time = round(query[3], 2)
                rows = query[4]

                print(
                    f"{query_text:<50} {calls:<8} {total_time:<12} {mean_time:<12} {rows}"
                )

            print("-" * 80)
        else:
            print("⚡ МЕДЛЕННЫЕ ЗАПРОСЫ")
            print("=" * 50)
            print("📝 Расширение pg_stat_statements не установлено")
            print("   Для получения статистики запросов установите:")
            print("   CREATE EXTENSION pg_stat_statements;")
            print("-" * 50)

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

        print("\n🔒 БЛОКИРОВКИ")
        print(f"   • Активные: {lock_stats[0]}")
        print(f"   • Ожидающие: {lock_stats[1]}")

        # Дополнительная статистика
        table_stats_q = text(
            """
            SELECT
                schemaname,
                relname as tablename,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes,
                n_live_tup as live_rows,
                n_dead_tup as dead_rows
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            AND relname IN ('ohlcv_p', 'indicators_p', 'instruments')
            ORDER BY n_live_tup DESC
        """
        )
        result = await session.execute(table_stats_q)
        table_stats = result.fetchall()

        print("\n📊 СТАТИСТИКА ТАБЛИЦ")
        print("=" * 70)
        print(
            f"{'Таблица':<15} {'Вставки':<8} {'Обновления':<10} {'Удаления':<8} {'Живые строки':<12} {'Мёртвые строки':<12}"
        )
        print("-" * 70)

        for table in table_stats:
            table_name = table[1]
            inserts = table[2] or 0
            updates = table[3] or 0
            deletes = table[4] or 0
            live_rows = table[5] or 0
            dead_rows = table[6] or 0

            print(
                f"{table_name:<15} {inserts:<8} {updates:<10} {deletes:<8} {live_rows:<12} {dead_rows:<12}"
            )

        print("-" * 70)


def main():
    """Главная функция CLI."""
    parser = argparse.ArgumentParser(description="CLI для работы с отчётами миграций")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Команда status
    subparsers.add_parser("status", help="Показать статус миграций")

    # Команда health
    subparsers.add_parser("health", help="Показать состояние системы")

    # Команда report
    report_parser = subparsers.add_parser(
        "report", help="Сгенерировать отчёт для миграции"
    )
    report_parser.add_argument("migration_id", help="ID миграции")
    report_parser.add_argument(
        "--duration", type=int, help="Длительность в миллисекундах"
    )

    # Команда stats
    subparsers.add_parser("stats", help="Показать статистику БД")

    # Команда performance
    subparsers.add_parser("performance", help="Показать метрики производительности")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Выполняем команду
    if args.command == "status":
        asyncio.run(show_migration_status())
    elif args.command == "health":
        asyncio.run(show_system_health())
    elif args.command == "report":
        asyncio.run(generate_report_for_migration(args.migration_id, args.duration))
    elif args.command == "stats":
        asyncio.run(show_database_stats())
    elif args.command == "performance":
        asyncio.run(show_performance_metrics())


if __name__ == "__main__":
    main()
