"""
MTF Database Migration Command

CLI команда для управления миграциями базы данных MTF системы.
"""

import os
from typing import TYPE_CHECKING

from src.mtf.logging_config import get_main_logger

if TYPE_CHECKING:
    from src.mtf.database.client import MTFDatabaseClient
    from src.mtf.database.migrations import MTFDatabaseMigrations

logger = get_main_logger()


def register(subparsers):
    """Регистрация команды mtf-migrate"""
    mtf_migrate_parser = subparsers.add_parser(
        "mtf-migrate", help="Управление миграциями базы данных MTF системы"
    )

    mtf_migrate_parser.add_argument(
        "--action",
        choices=["run", "check", "cleanup", "stats"],
        default="run",
        help="Действие для выполнения (run, check, cleanup, stats)",
    )

    mtf_migrate_parser.add_argument(
        "--database-url", help="URL подключения к базе данных"
    )

    mtf_migrate_parser.add_argument(
        "--days-to-keep",
        type=int,
        default=30,
        help="Количество дней для хранения данных при cleanup",
    )

    mtf_migrate_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Подробный вывод"
    )

    mtf_migrate_parser.set_defaults(_handler=handle_mtf_migrate)


async def handle_mtf_migrate(args) -> None:
    """Обработка команды mtf-migrate"""
    logger.info(f"MTF Migration: {args.action}")

    try:
        # Получение URL базы данных
        database_url = args.database_url or os.getenv("DATABASE_URL")
        if not database_url:
            logger.error(
                "Database URL not provided. Use --database-url or set DATABASE_URL environment variable"
            )
            return

        # Импорт модулей MTF
        from src.mtf.database.client import MTFDatabaseClient
        from src.mtf.database.migrations import MTFDatabaseMigrations

        # Инициализация
        migrations = MTFDatabaseMigrations(database_url)
        db_client = MTFDatabaseClient(database_url)
        await db_client.initialize()

        if args.action == "run":
            await handle_run_migrations(migrations, args.verbose)
        elif args.action == "check":
            await handle_check_tables(migrations, args.verbose)
        elif args.action == "cleanup":
            await handle_cleanup_data(migrations, args.days_to_keep, args.verbose)
        elif args.action == "stats":
            await handle_get_stats(db_client, args.verbose)

        await db_client.close()
        logger.info("MTF Migration completed successfully")

    except Exception as e:
        logger.error(f"MTF Migration failed: {e}")
        raise


async def handle_run_migrations(
    migrations: "MTFDatabaseMigrations", verbose: bool
) -> None:
    """Запуск миграций"""
    logger.info("Running MTF database migrations...")

    success = await migrations.run_migrations()

    if success:
        logger.info("Migrations completed successfully")

        if verbose:
            # Проверяем созданные таблицы
            tables_exist = await migrations.check_tables_exist()
            logger.info("Tables status:")
            for table, exists in tables_exist.items():
                status = "EXISTS" if exists else "MISSING"
                logger.info(f"  - {table}: {status}")
    else:
        logger.error("Migrations failed")
        raise Exception("Migration failed")


async def handle_check_tables(
    migrations: "MTFDatabaseMigrations", verbose: bool
) -> None:
    """Проверка существования таблиц"""
    logger.info("Checking MTF database tables...")

    tables_exist = await migrations.check_tables_exist()

    logger.info("Tables status:")
    all_exist = True
    for table, exists in tables_exist.items():
        status = "EXISTS" if exists else "MISSING"
        logger.info(f"  - {table}: {status}")
        if not exists:
            all_exist = False

    if all_exist:
        logger.info("All MTF tables exist")
    else:
        logger.warning("Some MTF tables are missing. Run migrations with 'run' action.")

    if verbose:
        # Показываем структуру таблиц
        for table in tables_exist:
            if tables_exist[table]:
                logger.info(f"\nTable structure for {table}:")
                table_info = await migrations.get_table_info(table)
                for column in table_info:
                    logger.info(
                        f"  - {column['column_name']}: {column['data_type']} "
                        f"({'NULL' if column['is_nullable'] == 'YES' else 'NOT NULL'})"
                    )


async def handle_cleanup_data(
    migrations: "MTFDatabaseMigrations", days_to_keep: int, verbose: bool
) -> None:
    """Очистка старых данных"""
    logger.info(f"Cleaning up MTF data older than {days_to_keep} days...")

    await migrations.cleanup_old_data(days_to_keep)

    logger.info("Data cleanup completed")

    if verbose:
        # Показываем статистику после очистки
        logger.info("Table statistics after cleanup:")
        tables = [
            "mtf_context",
            "mtf_triggers",
            "mtf_consensus",
            "mtf_pipeline",
            "mtf_integration",
        ]
        for table in tables:
            stats = await migrations.get_table_stats(table)
            if stats:
                logger.info(
                    f"  - {table}: {stats.get('row_count', 0)} rows, "
                    f"earliest: {stats.get('earliest_record', 'N/A')}, "
                    f"latest: {stats.get('latest_record', 'N/A')}"
                )


async def handle_get_stats(db_client: "MTFDatabaseClient", verbose: bool) -> None:
    """Получение статистики"""
    logger.info("Getting MTF system statistics...")

    try:
        # Получение последних результатов
        latest_results = await db_client.get_latest_results()
        logger.info(f"Latest results: {len(latest_results)} symbols")

        if latest_results:
            logger.info("Latest results by symbol:")
            for result in latest_results[:10]:  # Показываем первые 10
                logger.info(
                    f"  - {result.symbol}: {result.consensus_type} "
                    f"(confidence: {result.confidence_level}, "
                    f"regime: {result.dominant_regime})"
                )

        # Получение статистики по часам
        statistics = await db_client.get_statistics(hours=24)
        logger.info(f"Statistics for last 24 hours: {len(statistics)} hours")

        if statistics:
            total_processed = sum(stat["total_processed"] for stat in statistics)
            total_successful = sum(stat["successful"] for stat in statistics)
            total_failed = sum(stat["failed"] for stat in statistics)

            logger.info(f"  - Total processed: {total_processed}")
            logger.info(f"  - Successful: {total_successful}")
            logger.info(f"  - Failed: {total_failed}")
            logger.info(
                f"  - Success rate: {(total_successful/total_processed*100):.1f}%"
                if total_processed > 0
                else "  - Success rate: N/A"
            )

            if verbose:
                logger.info("Hourly breakdown:")
                for stat in statistics[:12]:  # Показываем последние 12 часов
                    logger.info(
                        f"  - {stat['hour']}: {stat['total_processed']} processed, "
                        f"{stat['successful']} successful, "
                        f"{stat.get('strong_bullish_signals', 0)} strong bullish, "
                        f"{stat.get('strong_bearish_signals', 0)} strong bearish"
                    )

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise
