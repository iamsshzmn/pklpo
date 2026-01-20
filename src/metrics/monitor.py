"""
Мониторинг системы и автоматический сбор метрик
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psutil

from .collector import MetricsCollector, MetricType, metrics_collector

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """Системные метрики"""

    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_usage_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    timestamp: datetime


class MetricsMonitor:
    """Мониторинг системы и автоматический сбор метрик"""

    def __init__(self, collector: MetricsCollector, interval_seconds: int = 30):
        self.collector = collector
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._monitoring_task: asyncio.Task | None = None
        self._last_network_stats = None

    async def start_monitoring(self) -> None:
        """Запускает мониторинг"""
        if self.is_running:
            logger.warning("Мониторинг уже запущен")
            return

        self.is_running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Запущен мониторинг с интервалом {self.interval_seconds} секунд")

    async def stop_monitoring(self) -> None:
        """Останавливает мониторинг"""
        if not self.is_running:
            return

        self.is_running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task

        logger.info("Мониторинг остановлен")

    async def _monitoring_loop(self) -> None:
        """Основной цикл мониторинга"""
        while self.is_running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(5)  # Пауза перед повторной попыткой

    async def _collect_system_metrics(self) -> None:
        """Собирает системные метрики"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            await self.collector.set_gauge("system_cpu_percent", cpu_percent)

            # Memory
            memory = psutil.virtual_memory()
            await self.collector.set_gauge("system_memory_percent", memory.percent)
            await self.collector.set_gauge(
                "system_memory_used_mb", memory.used / 1024 / 1024
            )
            await self.collector.set_gauge(
                "system_memory_total_mb", memory.total / 1024 / 1024
            )

            # Disk
            disk = psutil.disk_usage("/")
            await self.collector.set_gauge("system_disk_usage_percent", disk.percent)
            await self.collector.set_gauge(
                "system_disk_used_gb", disk.used / 1024 / 1024 / 1024
            )
            await self.collector.set_gauge(
                "system_disk_total_gb", disk.total / 1024 / 1024 / 1024
            )

            # Network
            network = psutil.net_io_counters()
            if self._last_network_stats:
                bytes_sent_diff = (
                    network.bytes_sent - self._last_network_stats.bytes_sent
                )
                bytes_recv_diff = (
                    network.bytes_recv - self._last_network_stats.bytes_recv
                )

                await self.collector.observe_histogram(
                    "system_network_bytes_sent_per_sec",
                    bytes_sent_diff / self.interval_seconds,
                )
                await self.collector.observe_histogram(
                    "system_network_bytes_recv_per_sec",
                    bytes_recv_diff / self.interval_seconds,
                )

            self._last_network_stats = network

            # Process-specific metrics
            await self._collect_process_metrics()

        except Exception as e:
            logger.error(f"Ошибка при сборе системных метрик: {e}")

    async def _collect_process_metrics(self) -> None:
        """Собирает метрики текущего процесса"""
        try:
            process = psutil.Process()

            # CPU и Memory процесса
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()

            await self.collector.set_gauge("process_cpu_percent", cpu_percent)
            await self.collector.set_gauge(
                "process_memory_mb", memory_info.rss / 1024 / 1024
            )
            await self.collector.set_gauge(
                "process_memory_percent", process.memory_percent()
            )

            # Количество открытых файлов
            try:
                open_files = len(process.open_files())
                await self.collector.set_gauge("process_open_files", open_files)
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass

            # Количество потоков
            try:
                num_threads = process.num_threads()
                await self.collector.set_gauge("process_threads", num_threads)
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass

        except Exception as e:
            logger.error(f"Ошибка при сборе метрик процесса: {e}")

    async def get_system_health(self) -> dict[str, Any]:
        """Получает состояние здоровья системы"""
        try:
            # Получаем последние метрики
            cpu_summary = await self.collector.get_metric_summary(
                "system_cpu_percent", 5
            )
            memory_summary = await self.collector.get_metric_summary(
                "system_memory_percent", 5
            )
            disk_summary = await self.collector.get_metric_summary(
                "system_disk_usage_percent", 5
            )

            health_status = {
                "timestamp": datetime.utcnow(),
                "overall_status": "healthy",
                "warnings": [],
                "critical_issues": [],
            }

            # Проверяем CPU
            if cpu_summary and cpu_summary["avg"] > 80:
                health_status["warnings"].append(
                    f"Высокое использование CPU: {cpu_summary['avg']:.1f}%"
                )
                if cpu_summary["avg"] > 95:
                    health_status["critical_issues"].append(
                        f"Критическое использование CPU: {cpu_summary['avg']:.1f}%"
                    )
                    health_status["overall_status"] = "critical"

            # Проверяем Memory
            if memory_summary and memory_summary["avg"] > 85:
                health_status["warnings"].append(
                    f"Высокое использование памяти: {memory_summary['avg']:.1f}%"
                )
                if memory_summary["avg"] > 95:
                    health_status["critical_issues"].append(
                        f"Критическое использование памяти: {memory_summary['avg']:.1f}%"
                    )
                    health_status["overall_status"] = "critical"

            # Проверяем Disk
            if disk_summary and disk_summary["avg"] > 90:
                health_status["warnings"].append(
                    f"Высокое использование диска: {disk_summary['avg']:.1f}%"
                )
                if disk_summary["avg"] > 95:
                    health_status["critical_issues"].append(
                        f"Критическое использование диска: {disk_summary['avg']:.1f}%"
                    )
                    health_status["overall_status"] = "critical"

            # Если есть критические проблемы, меняем статус
            if health_status["critical_issues"]:
                health_status["overall_status"] = "critical"
            elif health_status["warnings"]:
                health_status["overall_status"] = "warning"

            return health_status

        except Exception as e:
            logger.error(f"Ошибка при получении состояния здоровья системы: {e}")
            return {
                "timestamp": datetime.utcnow(),
                "overall_status": "unknown",
                "warnings": [f"Ошибка мониторинга: {e}"],
                "critical_issues": [],
            }

    async def register_custom_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> None:
        """Регистрирует пользовательскую метрику"""
        await self.collector.register_metric(name, metric_type, description, labels)

    async def track_database_metrics(self, session) -> None:
        """Отслеживает метрики базы данных"""
        try:
            # Количество записей в таблицах
            tables = ["ohlcv", "indicators", "signals", "signals_detailed"]

            for table in tables:
                try:
                    result = await session.execute(f"SELECT COUNT(*) FROM {table}")
                    count = result.scalar()
                    await self.collector.set_gauge(
                        "database_table_records", count, {"table": table}
                    )
                except Exception as e:
                    logger.warning(
                        f"Не удалось получить количество записей для таблицы {table}: {e}"
                    )

            # Размер таблиц
            for table in tables:
                try:
                    result = await session.execute(
                        f"""
                        SELECT pg_size_pretty(pg_total_relation_size('{table}')) as size
                    """
                    )
                    size_str = result.scalar()
                    # Парсим размер (например, "1 MB" -> 1.0)
                    if size_str:
                        size_parts = size_str.split()
                        if len(size_parts) == 2:
                            size_value = float(size_parts[0])
                            unit = size_parts[1].upper()
                            # Конвертируем в MB
                            if unit == "KB":
                                size_mb = size_value / 1024
                            elif unit == "MB":
                                size_mb = size_value
                            elif unit == "GB":
                                size_mb = size_value * 1024
                            else:
                                size_mb = size_value

                            await self.collector.set_gauge(
                                "database_table_size_mb", size_mb, {"table": table}
                            )
                except Exception as e:
                    logger.warning(f"Не удалось получить размер таблицы {table}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при отслеживании метрик БД: {e}")


# Глобальный экземпляр монитора
metrics_monitor = MetricsMonitor(metrics_collector)
