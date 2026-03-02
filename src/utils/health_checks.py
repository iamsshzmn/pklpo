"""
Утилиты для health checks
"""

import asyncio
import logging
import time

from sqlalchemy import text

from src.okx.market import OKXMarket
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


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
        status_str = "✅" if self.status else "❌"
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
                    # Если функция вернула bool, создаем результат
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
                logger.error(f"Ошибка в health check {name}: {e}")
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


# Функции health checks
async def check_database_connection() -> HealthCheckResult:
    """
    Проверяет подключение к базе данных

    Returns:
        HealthCheckResult: Результат проверки
    """
    try:
        async with get_db_session() as session:
            # Выполняем простой запрос
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
    required_tables = ["instruments", "ohlcv", "indicators", "signals"]
    missing_tables = []

    try:
        async with get_db_session() as session:
            for table in required_tables:
                try:
                    result = await session.execute(
                        text(f"SELECT COUNT(*) FROM {table} LIMIT 1")
                    )
                    count = result.scalar()
                    logger.debug(f"Table {table}: {count} records")
                except Exception as e:
                    missing_tables.append(table)
                    logger.warning(f"Table {table} check failed: {e}")

            if not missing_tables:
                return HealthCheckResult(
                    name="Database Tables",
                    status=True,
                    message="All required tables are accessible",
                    details={"tables_checked": len(required_tables)},
                )
            return HealthCheckResult(
                name="Database Tables",
                status=False,
                message=f"Missing or inaccessible tables: {', '.join(missing_tables)}",
                details={"missing_tables": missing_tables},
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
            # Проверяем последние данные OHLCV
            result = await session.execute(text("SELECT MAX(ts) FROM ohlcv"))
            latest_ohlcv = result.scalar()

            # Проверяем последние данные indicators
            result = await session.execute(text("SELECT MAX(ts) FROM indicators"))
            latest_indicators = result.scalar()

            current_time = int(time.time() * 1000)  # Текущее время в миллисекундах
            max_age_hours = 24  # Максимальный возраст данных в часах
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
                # Индикаторы используют timestamp в секундах, а не миллисекундах
                age_indicators = (current_time // 1000) - latest_indicators
                if age_indicators > (max_age_hours * 60 * 60):
                    issues.append(
                        f"Indicators data is {age_indicators // (60 * 60)} hours old"
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
        async with OKXMarket() as client:
            # Выполняем простой запрос к API
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

        # Проверяем использование памяти
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        # Проверяем использование CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # Проверяем диск
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


# Создаем глобальный экземпляр health checker
health_checker = HealthChecker()

# Добавляем стандартные проверки
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

    print("\n🏥 HEALTH CHECK REPORT")
    print(f"Overall Status: {'✅ HEALTHY' if overall_status else '❌ UNHEALTHY'}")
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
