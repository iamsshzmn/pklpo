import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


class MigrationTestResult:
    """Результат тестирования миграции."""

    def __init__(
        self, test_name: str, success: bool, duration_ms: int, details: str = ""
    ):
        self.test_name = test_name
        self.success = success
        self.duration_ms = duration_ms
        self.details = details
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class MigrationTestSuite:
    """Набор тестов для миграций."""

    def __init__(self):
        self.results: list[MigrationTestResult] = []
        self.start_time = time.time()

    def add_result(self, result: MigrationTestResult):
        self.results.append(result)

    def get_summary(self) -> dict[str, Any]:
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        total_duration = sum(r.duration_ms for r in self.results)

        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (
                (passed_tests / total_tests * 100) if total_tests > 0 else 0
            ),
            "total_duration_ms": total_duration,
            "test_suite_duration_ms": int((time.time() - self.start_time) * 1000),
            "results": [r.to_dict() for r in self.results],
        }

    def save_report(self, filename: str = "migration_test_report.json"):
        """Сохраняет отчет в JSON файл."""
        summary = self.get_summary()
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        logger.info(f"📄 Отчет сохранен в {filename}")


async def test_schema_integrity() -> MigrationTestResult:
    """
    Тест 1: Проверка целостности схемы.
    """
    start_time = time.time()
    test_name = "Schema Integrity Test"

    try:
        async with get_db_session() as session:
            # Проверяем существование критичных таблиц
            critical_tables = [
                "ohlcv_p",
                "indicators_p",
                "instruments",
                "schema_migrations",
            ]
            missing_tables = []

            for table in critical_tables:
                check_q = text("SELECT to_regclass(:table) IS NOT NULL")
                exists = await session.execute(check_q, {"table": table})
                if not exists.scalar():
                    missing_tables.append(table)

            if missing_tables:
                details = f"Missing tables: {missing_tables}"
                success = False
            else:
                details = "All critical tables exist"
                success = True

            # Проверяем индексы
            index_check_q = text(
                """
                SELECT COUNT(*) FROM pg_indexes
                WHERE tablename IN ('ohlcv_p', 'indicators_p')
            """
            )
            index_count = await session.execute(index_check_q)
            index_count = index_count.scalar()

            if index_count == 0:
                details += "; No indexes found"
                success = False
            else:
                details += f"; Found {index_count} indexes"

            duration_ms = int((time.time() - start_time) * 1000)
            return MigrationTestResult(test_name, success, duration_ms, details)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return MigrationTestResult(test_name, False, duration_ms, f"Error: {e}")


async def test_idempotency() -> MigrationTestResult:
    """
    Тест 2: Тест идемпотентности (повторный запуск без изменений).
    """
    start_time = time.time()
    test_name = "Idempotency Test"

    try:
        async with get_db_session() as session:
            # Получаем количество миграций до теста
            before_q = text("SELECT COUNT(*) FROM schema_migrations")
            before_count = await session.execute(before_q)
            before_count = before_count.scalar()

            # Пытаемся создать уже существующий ENUM (должен не упасть)
            enum_q = text(
                """
                DO $$ BEGIN
                    CREATE TYPE test_idempotency_enum AS ENUM ('test');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """
            )
            await session.execute(enum_q)

            # Пытаемся создать уже существующий индекс (должен не упасть)
            index_q = text(
                "CREATE INDEX IF NOT EXISTS test_idempotency_idx ON instruments(symbol)"
            )
            await session.execute(index_q)

            # Получаем количество миграций после теста
            after_q = text("SELECT COUNT(*) FROM schema_migrations")
            after_count = await session.execute(after_q)
            after_count = after_count.scalar()

            # Проверяем, что количество миграций не изменилось
            if before_count == after_count:
                details = f"Migration count unchanged: {before_count}"
                success = True
            else:
                details = f"Migration count changed: {before_count} -> {after_count}"
                success = False

            # Очищаем тестовые объекты
            cleanup_type_q = text("DROP TYPE IF EXISTS test_idempotency_enum CASCADE;")
            await session.execute(cleanup_type_q)

            cleanup_index_q = text("DROP INDEX IF EXISTS test_idempotency_idx;")
            await session.execute(cleanup_index_q)

            duration_ms = int((time.time() - start_time) * 1000)
            return MigrationTestResult(test_name, success, duration_ms, details)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return MigrationTestResult(test_name, False, duration_ms, f"Error: {e}")


async def test_large_table_performance() -> MigrationTestResult:
    """
    Тест 3: Smoke-test на больших таблицах (время/блокировки).
    """
    start_time = time.time()
    test_name = "Large Table Performance Test"

    try:
        async with get_db_session() as session:
            # Проверяем размер таблиц
            size_q = text(
                """
                SELECT
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables
                WHERE tablename IN ('ohlcv_p', 'indicators_p')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """
            )

            sizes = await session.execute(size_q)
            size_results = sizes.fetchall()

            # Проверяем количество записей
            count_q = text(
                """
                SELECT
                    'ohlcv_p' as table_name,
                    COUNT(*) as record_count
                FROM ohlcv_p
                UNION ALL
                SELECT
                    'indicators_p' as table_name,
                    COUNT(*) as record_count
                FROM indicators_p
            """
            )

            counts = await session.execute(count_q)
            count_results = counts.fetchall()

            # Проверяем производительность запросов
            perf_start = time.time()
            perf_q = text(
                """
                SELECT symbol, timeframe, COUNT(*)
                FROM ohlcv_p
                WHERE timestamp > extract(epoch from now() - interval '7 days')
                GROUP BY symbol, timeframe
                LIMIT 10
            """
            )

            perf_result = await session.execute(perf_q)
            perf_rows = perf_result.fetchall()
            perf_duration = (time.time() - perf_start) * 1000

            # Формируем детали
            details = f"Tables: {len(size_results)}, Records: {sum(r[1] for r in count_results)}, "
            details += f"Query time: {perf_duration:.1f}ms, Results: {len(perf_rows)}"

            # Тест считается успешным, если запрос выполнился менее чем за 5 секунд
            success = perf_duration < 5000

            duration_ms = int((time.time() - start_time) * 1000)
            return MigrationTestResult(test_name, success, duration_ms, details)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return MigrationTestResult(test_name, False, duration_ms, f"Error: {e}")


async def test_constraints_validation() -> MigrationTestResult:
    """
    Тест 4: Проверка работы ограничений.
    """
    start_time = time.time()
    test_name = "Constraints Validation Test"

    try:
        async with get_db_session() as session:
            # Проверяем PRIMARY KEY ограничения
            pk_check_q = text(
                """
                SELECT
                    tc.table_name,
                    tc.constraint_name,
                    tc.constraint_type
                FROM information_schema.table_constraints tc
                WHERE tc.table_name IN ('ohlcv_p', 'indicators_p')
                AND tc.constraint_type = 'PRIMARY KEY'
            """
            )

            pk_results = await session.execute(pk_check_q)
            pk_count = len(pk_results.fetchall())

            # Проверяем CHECK ограничения
            check_q = text(
                """
                SELECT
                    tc.table_name,
                    tc.constraint_name,
                    tc.constraint_type
                FROM information_schema.table_constraints tc
                WHERE tc.table_name IN ('ohlcv_p', 'indicators_p', 'instruments')
                AND tc.constraint_type = 'CHECK'
            """
            )

            check_results = await session.execute(check_q)
            check_count = len(check_results.fetchall())

            # Проверяем UNIQUE ограничения
            unique_q = text(
                """
                SELECT
                    tc.table_name,
                    tc.constraint_name,
                    tc.constraint_type
                FROM information_schema.table_constraints tc
                WHERE tc.table_name IN ('ohlcv_p', 'indicators_p', 'instruments')
                AND tc.constraint_type = 'UNIQUE'
            """
            )

            unique_results = await session.execute(unique_q)
            unique_count = len(unique_results.fetchall())

            details = f"PK: {pk_count}, CHECK: {check_count}, UNIQUE: {unique_count}"
            success = pk_count >= 2 and check_count >= 3  # Минимальные ожидания

            duration_ms = int((time.time() - start_time) * 1000)
            return MigrationTestResult(test_name, success, duration_ms, details)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return MigrationTestResult(test_name, False, duration_ms, f"Error: {e}")


async def test_monitoring_functions() -> MigrationTestResult:
    """
    Тест 5: Проверка функций мониторинга.
    """
    start_time = time.time()
    test_name = "Monitoring Functions Test"

    try:
        async with get_db_session() as session:
            # Проверяем функцию создания бэкапа
            backup_q = text(
                "SELECT create_table_backup('instruments', 'test_monitoring')"
            )
            backup_result = await session.execute(backup_q)
            backup_table = backup_result.scalar()

            # Проверяем VIEW мониторинга
            monitoring_q = text("SELECT COUNT(*) FROM table_size_monitoring")
            monitoring_result = await session.execute(monitoring_q)
            monitoring_count = monitoring_result.scalar()

            # Проверяем функцию готовности к миграции
            readiness_q = text("SELECT * FROM check_migration_readiness('test')")
            readiness_result = await session.execute(readiness_q)
            readiness_rows = readiness_result.fetchall()

            # Очищаем тестовый бэкап
            cleanup_q = text(f"DROP TABLE IF EXISTS {backup_table}")
            await session.execute(cleanup_q)

            details = f"Backup: {backup_table}, Monitoring: {monitoring_count} tables, "
            details += f"Readiness checks: {len(readiness_rows)}"

            success = backup_table and monitoring_count > 0 and len(readiness_rows) > 0

            duration_ms = int((time.time() - start_time) * 1000)
            return MigrationTestResult(test_name, success, duration_ms, details)

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return MigrationTestResult(test_name, False, duration_ms, f"Error: {e}")


async def run_migration_test_suite() -> MigrationTestSuite:
    """
    Запускает полный набор тестов миграций.
    """
    logger.info("🧪 Запускаем тестовый набор миграций...")

    test_suite = MigrationTestSuite()

    # Запускаем все тесты
    tests = [
        test_schema_integrity,
        test_idempotency,
        test_large_table_performance,
        test_constraints_validation,
        test_monitoring_functions,
    ]

    for test_func in tests:
        logger.info(f"🔍 Запускаем тест: {test_func.__name__}")
        result = await test_func()
        test_suite.add_result(result)

        status = "✅ PASS" if result.success else "❌ FAIL"
        logger.info(
            f"{status} {result.test_name} ({result.duration_ms}ms): {result.details}"
        )

    # Выводим итоговую статистику
    summary = test_suite.get_summary()
    logger.info("📊 Итоговая статистика тестов:")
    logger.info(f"   Всего тестов: {summary['total_tests']}")
    logger.info(f"   Успешных: {summary['passed_tests']}")
    logger.info(f"   Неудачных: {summary['failed_tests']}")
    logger.info(f"   Процент успеха: {summary['success_rate']:.1f}%")
    logger.info(f"   Общее время: {summary['total_duration_ms']}ms")

    # Сохраняем отчет
    test_suite.save_report()

    return test_suite


async def run_ci_migration_test() -> bool:
    """
    Запускает тесты для CI/CD интеграции.
    Возвращает True если все тесты прошли успешно.
    """
    logger.info("🚀 Запуск CI/CD тестов миграций...")

    test_suite = await run_migration_test_suite()
    summary = test_suite.get_summary()

    # Для CI/CD считаем успешным только если все тесты прошли
    success = summary["failed_tests"] == 0

    if success:
        logger.info("✅ Все CI/CD тесты прошли успешно!")
    else:
        logger.error(f"❌ CI/CD тесты не прошли: {summary['failed_tests']} неудачных")

    return success


def main():
    """
    Главная функция для запуска тестов миграций.
    """
    import argparse
    import sys
    from pathlib import Path

    # Добавляем корневую директорию в путь для импортов
    sys.path.append(str(Path(__file__).parent.parent.parent))

    # Настраиваем логирование
    from src.logging_config import setup_logging

    setup_logging("migration_tests.log")

    parser = argparse.ArgumentParser(description="Тестирование миграций базы данных")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Режим CI/CD (возвращает код ошибки при неудачных тестах)",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="migration_test_report.json",
        help="Путь к файлу отчета (по умолчанию: migration_test_report.json)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        if args.ci:
            # CI/CD режим
            success = asyncio.run(run_ci_migration_test())
            if not success:
                logger.error("❌ Тесты не прошли в CI/CD режиме")
                sys.exit(1)
            logger.info("✅ Все тесты прошли успешно в CI/CD режиме")
        else:
            # Обычный режим
            test_suite = asyncio.run(run_migration_test_suite())
            test_suite.save_report(args.report)

            summary = test_suite.get_summary()
            if summary["failed_tests"] > 0:
                logger.warning(f"⚠️ {summary['failed_tests']} тестов не прошли")
                if args.ci:
                    sys.exit(1)
            else:
                logger.info("✅ Все тесты прошли успешно!")

    except KeyboardInterrupt:
        logger.info("🛑 Тестирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при тестировании: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
