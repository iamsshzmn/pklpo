"""
Утилиты для health checks
"""

import asyncio
import logging
import time

from sqlalchemy import text

from src.models import INDICATORS_TABLE_NAME
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def _is_partitioned_table(session, table_name: str) -> bool:
    result = await session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_partitioned_table pt
                JOIN pg_class c ON c.oid = pt.partrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return bool(result.scalar())


class HealthCheckResult:
    """Результат health check"""

    def __init__(
        self, name: str, status: bool, message: str = "", details: dict | None = None
    ):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = time.time()

    def __str__(self) -> str:
        status_str = "OK" if self.status else "FAIL"
        return f"{status_str} {self.name}: {self.message}"

    def to_dict(self) -> dict:
        """Преобразует результат в словарь"""
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class HealthChecker:
    """Класс для выполнения health checks"""

    def __init__(self):
        self.checks: list[tuple[str, callable]] = []

    def add_check(self, name: str, check_func: callable) -> None:
        """
        Добавляет health check

        Args:
            name: Название проверки
            check_func: Функция проверки
        """
        self.checks.append((name, check_func))

    async def run_all_checks(self) -> list[HealthCheckResult]:
        """
        Запускает все health checks

        Returns:
            List[HealthCheckResult]: Результаты всех проверок
        """
        results = []

        for name, check_func in self.checks:
            try:
                start_time = time.time()

                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()

                execution_time = time.time() - start_time

                if isinstance(result, HealthCheckResult):
                    result.details["execution_time"] = execution_time
                    results.append(result)
                else:
                    status = bool(result)
                    message = "OK" if status else "Failed"
                    health_result = HealthCheckResult(
                        name=name,
                        status=status,
                        message=message,
                        details={"execution_time": execution_time},
                    )
                    results.append(health_result)

            except Exception as e:
                logger.error("Ошибка в health check %s: %s", name, e)
                results.append(
                    HealthCheckResult(
                        name=name,
                        status=False,
                        message=f"Exception: {e!s}",
                        details={"error": str(e)},
                    )
                )

        return results

    def get_overall_status(self, results: list[HealthCheckResult]) -> bool:
        """
        Определяет общий статус всех проверок

        Args:
            results: Результаты проверок

        Returns:
            bool: True если все проверки прошли успешно
        """
        return all(result.status for result in results)


async def check_database_connection() -> HealthCheckResult:
    """
    Проверяет подключение к базе данных

    Returns:
        HealthCheckResult: Результат проверки
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()

            if value == 1:
                return HealthCheckResult(
                    name="Database Connection",
                    status=True,
                    message="Database connection is healthy",
                    details={"query_result": value},
                )
            return HealthCheckResult(
                name="Database Connection",
                status=False,
                message="Database query returned unexpected result",
                details={"query_result": value},
            )

    except Exception as e:
        return HealthCheckResult(
            name="Database Connection",
            status=False,
            message=f"Database connection failed: {e!s}",
            details={"error": str(e)},
        )


async def check_database_tables() -> HealthCheckResult:
    """
    Проверяет наличие основных таблиц

    Returns:
        HealthCheckResult: Результат проверки
    """
    required_table_groups = {
        "instruments": ["instruments"],
        "market_candles": ["swap_ohlcv_p", "ohlcv_p", "ohlcv"],
        "features": [INDICATORS_TABLE_NAME],
        "market_meta": ["market_data_ext"],
        "market_selection": [
            "market_scores_tf",
            "market_universe",
            "market_universe_versions",
            "market_regime_history",
        ],
    }
    missing_groups = []

    try:
        async with get_db_session() as session:
            for group_name, tables in required_table_groups.items():
                group_ok = False
                last_error: Exception | None = None

                for table in tables:
                    try:
                        if table == "swap_ohlcv_p" and not await _is_partitioned_table(
                            session, table
                        ):
                            last_error = RuntimeError(
                                "swap_ohlcv_p is present but not partitioned"
                            )
                            continue
                        result = await session.execute(
                            text(f"SELECT COUNT(*) FROM {table} LIMIT 1")
                        )
                        count = result.scalar()
                        logger.debug("Table %s: %s records", table, count)
                        group_ok = True
                        break
                    except Exception as e:
                        last_error = e

                if not group_ok:
                    missing_groups.append(group_name)
                    if last_error is not None:
                        logger.warning(
                            "Table group %s check failed for %s: %s",
                            group_name,
                            tables,
                            last_error,
                        )

            if not missing_groups:
                return HealthCheckResult(
                    name="Database Tables",
                    status=True,
                    message="All required table groups are accessible",
                    details={"table_groups_checked": len(required_table_groups)},
                )
            return HealthCheckResult(
                name="Database Tables",
                status=False,
                message=f"Missing or inaccessible table groups: {', '.join(missing_groups)}",
                details={"missing_groups": missing_groups},
            )

    except Exception as e:
        return HealthCheckResult(
            name="Database Tables",
            status=False,
            message=f"Database tables check failed: {e!s}",
            details={"error": str(e)},
        )


async def check_database_data_freshness() -> HealthCheckResult:
    """
    Проверяет свежесть данных в базе

    Returns:
        HealthCheckResult: Результат проверки
    """
    try:
        async with get_db_session() as session:
            latest_ohlcv = None
            for query in (
                "SELECT MAX(timestamp) FROM swap_ohlcv_p",
                "SELECT MAX(timestamp) FROM ohlcv_p",
                "SELECT MAX(ts) FROM ohlcv",
            ):
                try:
                    result = await session.execute(text(query))
                    latest_ohlcv = result.scalar()
                    if latest_ohlcv is not None:
                        break
                except Exception as e:
                    logger.debug("Freshness query failed for '%s': %s", query, e)
                    continue

            result = await session.execute(
                text(f"SELECT MAX(timestamp) FROM {INDICATORS_TABLE_NAME}")
            )
            latest_indicators = result.scalar()

            current_time = int(time.time() * 1000)
            max_age_hours = 24
            max_age_ms = max_age_hours * 60 * 60 * 1000

            issues = []

            if latest_ohlcv:
                age_ohlcv = current_time - latest_ohlcv
                if age_ohlcv > max_age_ms:
                    issues.append(
                        f"OHLCV data is {age_ohlcv // (60 * 60 * 1000)} hours old"
                    )
            else:
                issues.append("No OHLCV data found")

            if latest_indicators:
                age_indicators = current_time - latest_indicators
                if age_indicators > max_age_ms:
                    issues.append(
                        "Indicators data is "
                        f"{age_indicators // (60 * 60 * 1000)} hours old"
                    )
            else:
                issues.append("No indicators data found")

            if not issues:
                return HealthCheckResult(
                    name="Data Freshness",
                    status=True,
                    message="Data is fresh",
                    details={
                        "latest_ohlcv": latest_ohlcv,
                        "latest_indicators": latest_indicators,
                        "current_time": current_time,
                    },
                )
            return HealthCheckResult(
                name="Data Freshness",
                status=False,
                message=f"Data freshness issues: {'; '.join(issues)}",
                details={
                    "issues": issues,
                    "latest_ohlcv": latest_ohlcv,
                    "latest_indicators": latest_indicators,
                    "current_time": current_time,
                },
            )

    except Exception as e:
        return HealthCheckResult(
            name="Data Freshness",
            status=False,
            message=f"Data freshness check failed: {e!s}",
            details={"error": str(e)},
        )


async def check_okx_api() -> HealthCheckResult:
    """
    Проверяет доступность OKX API

    Returns:
        HealthCheckResult: Результат проверки
    """
    try:
        from src.candles.infrastructure import OKXMarket

        async with OKXMarket() as client:
            instruments = await client.get_instruments("SPOT")

            if instruments and len(instruments) > 0:
                return HealthCheckResult(
                    name="OKX API",
                    status=True,
                    message="OKX API is accessible",
                    details={"instruments_count": len(instruments)},
                )
            return HealthCheckResult(
                name="OKX API",
                status=False,
                message="OKX API returned empty response",
                details={"instruments_count": 0},
            )

    except Exception as e:
        return HealthCheckResult(
            name="OKX API",
            status=False,
            message=f"OKX API check failed: {e!s}",
            details={"error": str(e)},
        )


async def check_system_resources() -> HealthCheckResult:
    """
    Проверяет системные ресурсы

    Returns:
        HealthCheckResult: Результат проверки
    """
    try:
        import psutil

        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        cpu_percent = psutil.cpu_percent(interval=1)

        disk = psutil.disk_usage("/")
        disk_percent = disk.percent

        issues = []

        if memory_percent > 90:
            issues.append(f"High memory usage: {memory_percent:.1f}%")

        if cpu_percent > 90:
            issues.append(f"High CPU usage: {cpu_percent:.1f}%")

        if disk_percent > 90:
            issues.append(f"High disk usage: {disk_percent:.1f}%")

        if not issues:
            return HealthCheckResult(
                name="System Resources",
                status=True,
                message="System resources are healthy",
                details={
                    "memory_percent": memory_percent,
                    "cpu_percent": cpu_percent,
                    "disk_percent": disk_percent,
                },
            )
        return HealthCheckResult(
            name="System Resources",
            status=False,
            message=f"Resource issues: {'; '.join(issues)}",
            details={
                "issues": issues,
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
                "disk_percent": disk_percent,
            },
        )

    except ImportError:
        return HealthCheckResult(
            name="System Resources",
            status=False,
            message="psutil not available for system resource check",
            details={"error": "psutil not installed"},
        )
    except Exception as e:
        return HealthCheckResult(
            name="System Resources",
            status=False,
            message=f"System resources check failed: {e!s}",
            details={"error": str(e)},
        )


health_checker = HealthChecker()
health_checker.add_check("Database Connection", check_database_connection)
health_checker.add_check("Database Tables", check_database_tables)
health_checker.add_check("Data Freshness", check_database_data_freshness)
health_checker.add_check("OKX API", check_okx_api)
health_checker.add_check("System Resources", check_system_resources)


async def run_health_checks() -> dict:
    """
    Запускает все health checks и возвращает результат

    Returns:
        Dict: Результаты всех проверок
    """
    results = await health_checker.run_all_checks()
    overall_status = health_checker.get_overall_status(results)

    return {
        "overall_status": overall_status,
        "timestamp": time.time(),
        "checks": [result.to_dict() for result in results],
    }


async def print_health_report() -> None:
    """Выводит отчет о состоянии системы"""
    results = await health_checker.run_all_checks()
    overall_status = health_checker.get_overall_status(results)

    print("\nHEALTH CHECK REPORT")
    print(f"Overall Status: {'HEALTHY' if overall_status else 'UNHEALTHY'}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    for result in results:
        print(f"{result}")
        if result.details:
            for key, value in result.details.items():
                if key != "execution_time":
                    print(f"  {key}: {value}")

    print("-" * 50)
    print(f"Total checks: {len(results)}")
    print(f"Passed: {sum(1 for r in results if r.status)}")
    print(f"Failed: {sum(1 for r in results if not r.status)}")


if __name__ == "__main__":
    asyncio.run(print_health_report())
