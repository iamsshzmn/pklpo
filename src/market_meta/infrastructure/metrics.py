"""
Система метрик и мониторинга для модуля market_meta.

Отслеживает:
- Cache hit ratio
- Validation success/failure rates
- API latency
- Error rates
- Performance metrics
"""

import asyncio
import json
import threading
import time
from collections import deque
from contextlib import asynccontextmanager, contextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .config import get_config
from .logging_config import get_logger

logger = get_logger("metrics")


@dataclass
class MetricPoint:
    """Точка метрики с временной меткой"""

    timestamp: datetime
    value: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Серия метрик"""

    name: str
    description: str
    unit: str
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    labels: dict[str, str] = field(default_factory=dict)

    def add_point(self, value: float, labels: dict[str, str] | None = None):
        """Добавляет точку метрики"""
        point = MetricPoint(timestamp=datetime.now(), value=value, labels=labels or {})
        self.points.append(point)

    def get_latest(self) -> MetricPoint | None:
        """Возвращает последнюю точку метрики"""
        return self.points[-1] if self.points else None

    def get_average(self, minutes: int = 5) -> float | None:
        """Возвращает среднее значение за последние N минут"""
        if not self.points:
            return None

        cutoff = datetime.now() - timedelta(minutes=minutes)
        recent_points = [p for p in self.points if p.timestamp >= cutoff]

        if not recent_points:
            return None

        return sum(p.value for p in recent_points) / len(recent_points)

    def get_count(self, minutes: int = 5) -> int:
        """Возвращает количество точек за последние N минут"""
        if not self.points:
            return 0

        cutoff = datetime.now() - timedelta(minutes=minutes)
        return len([p for p in self.points if p.timestamp >= cutoff])


class MetricsCollector:
    """Сборщик метрик"""

    def __init__(self):
        self.config = get_config()
        self.metrics: dict[str, MetricSeries] = {}
        self._lock = threading.Lock()
        self._enabled = self.config.metrics.enabled

        # Инициализируем базовые метрики
        self._init_metrics()

    def _init_metrics(self):
        """Инициализирует базовые метрики"""
        # Cache метрики
        self._register_metric("cache_hit_ratio", "Cache hit ratio", "percent")
        self._register_metric("cache_miss_count", "Cache miss count", "count")
        self._register_metric("cache_hit_count", "Cache hit count", "count")
        self._register_metric(
            "cache_refresh_duration", "Cache refresh duration", "seconds"
        )

        # Validation метрики
        self._register_metric(
            "validation_success_rate", "Validation success rate", "percent"
        )
        self._register_metric(
            "validation_failure_count", "Validation failure count", "count"
        )
        self._register_metric(
            "validation_success_count", "Validation success count", "count"
        )
        self._register_metric("validation_duration", "Validation duration", "seconds")

        # API метрики
        self._register_metric("api_request_duration", "API request duration", "seconds")
        self._register_metric("api_request_count", "API request count", "count")
        self._register_metric("api_error_count", "API error count", "count")
        self._register_metric("api_success_rate", "API success rate", "percent")

        # OKX интеграция метрики
        self._register_metric("okx_request_duration", "OKX request duration", "seconds")
        self._register_metric("okx_retry_count", "OKX retry count", "count")
        self._register_metric("okx_rate_limit_hits", "OKX rate limit hits", "count")
        self._register_metric(
            "okx_instruments_loaded", "OKX instruments loaded", "count"
        )

        # Общие метрики
        self._register_metric("memory_usage_mb", "Memory usage", "MB")
        self._register_metric("active_connections", "Active connections", "count")
        self._register_metric("error_rate", "Error rate", "percent")

    def _register_metric(self, name: str, description: str, unit: str):
        """Регистрирует новую метрику"""
        with self._lock:
            self.metrics[name] = MetricSeries(name, description, unit)

    def record_cache_hit(self):
        """Записывает cache hit"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["cache_hit_count"].add_point(1)
            self._update_cache_hit_ratio()

    def record_cache_miss(self):
        """Записывает cache miss"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["cache_miss_count"].add_point(1)
            self._update_cache_hit_ratio()

    def _update_cache_hit_ratio(self):
        """Обновляет cache hit ratio"""
        hit_metric = self.metrics["cache_hit_count"]
        miss_metric = self.metrics["cache_miss_count"]

        hit_count = hit_metric.get_count(minutes=5)
        miss_count = miss_metric.get_count(minutes=5)
        total = hit_count + miss_count

        if total > 0:
            ratio = (hit_count / total) * 100
            self.metrics["cache_hit_ratio"].add_point(ratio)

    def record_validation_success(self, duration: float = 0.0):
        """Записывает успешную валидацию"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["validation_success_count"].add_point(1)
            if duration > 0:
                self.metrics["validation_duration"].add_point(duration)
            self._update_validation_success_rate()

    def record_validation_failure(self, duration: float = 0.0):
        """Записывает неудачную валидацию"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["validation_failure_count"].add_point(1)
            if duration > 0:
                self.metrics["validation_duration"].add_point(duration)
            self._update_validation_success_rate()

    def _update_validation_success_rate(self):
        """Обновляет success rate валидации"""
        success_metric = self.metrics["validation_success_count"]
        failure_metric = self.metrics["validation_failure_count"]

        success_count = success_metric.get_count(minutes=5)
        failure_count = failure_metric.get_count(minutes=5)
        total = success_count + failure_count

        if total > 0:
            rate = (success_count / total) * 100
            self.metrics["validation_success_rate"].add_point(rate)

    def record_api_request(self, duration: float, success: bool = True):
        """Записывает API запрос"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["api_request_count"].add_point(1)
            self.metrics["api_request_duration"].add_point(duration)

            if not success:
                self.metrics["api_error_count"].add_point(1)

            self._update_api_success_rate()

    def _update_api_success_rate(self):
        """Обновляет API success rate"""
        request_metric = self.metrics["api_request_count"]
        error_metric = self.metrics["api_error_count"]

        request_count = request_metric.get_count(minutes=5)
        error_count = error_metric.get_count(minutes=5)

        if request_count > 0:
            rate = ((request_count - error_count) / request_count) * 100
            self.metrics["api_success_rate"].add_point(rate)

    def record_okx_request(
        self, duration: float, retries: int = 0, rate_limited: bool = False
    ):
        """Записывает OKX запрос"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["okx_request_duration"].add_point(duration)

            if retries > 0:
                self.metrics["okx_retry_count"].add_point(retries)

            if rate_limited:
                self.metrics["okx_rate_limit_hits"].add_point(1)

    def record_instruments_loaded(self, count: int):
        """Записывает количество загруженных инструментов"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["okx_instruments_loaded"].add_point(count)

    def record_memory_usage(self, usage_mb: float):
        """Записывает использование памяти"""
        if not self._enabled:
            return

        with self._lock:
            self.metrics["memory_usage_mb"].add_point(usage_mb)

    def record_error(self):
        """Записывает ошибку"""
        if not self._enabled:
            return

        with self._lock:
            # Обновляем общий error rate
            total_requests = self.metrics["api_request_count"].get_count(minutes=5)
            error_count = self.metrics["api_error_count"].get_count(minutes=5)

            if total_requests > 0:
                error_rate = (error_count / total_requests) * 100
                self.metrics["error_rate"].add_point(error_rate)

    def get_metric(self, name: str) -> MetricSeries | None:
        """Возвращает метрику по имени"""
        return self.metrics.get(name)

    def get_all_metrics(self) -> dict[str, MetricSeries]:
        """Возвращает все метрики"""
        return self.metrics.copy()

    def get_metrics_summary(self) -> dict[str, Any]:
        """Возвращает сводку метрик"""
        summary = {}

        for name, metric in self.metrics.items():
            latest = metric.get_latest()
            average_5m = metric.get_average(minutes=5)
            count_5m = metric.get_count(minutes=5)

            summary[name] = {
                "latest": latest.value if latest else None,
                "latest_timestamp": latest.timestamp.isoformat() if latest else None,
                "average_5m": average_5m,
                "count_5m": count_5m,
                "unit": metric.unit,
                "description": metric.description,
            }

        return summary

    def export_metrics(self, format: str = "json") -> str:
        """Экспортирует метрики в указанном формате"""
        if format == "json":
            return json.dumps(self.get_metrics_summary(), indent=2, default=str)
        if format == "prometheus":
            return self._export_prometheus()
        raise ValueError(f"Unsupported format: {format}")

    def _export_prometheus(self) -> str:
        """Экспортирует метрики в формате Prometheus"""
        lines = []

        for name, metric in self.metrics.items():
            latest = metric.get_latest()
            if latest:
                # Создаем метки
                labels = ",".join([f'{k}="{v}"' for k, v in latest.labels.items()])
                label_str = f"{{{labels}}}" if labels else ""

                # Добавляем метрику
                lines.append(f"# HELP {name} {metric.description}")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name}{label_str} {latest.value}")

        return "\n".join(lines)


# Глобальный экземпляр сборщика метрик
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Возвращает глобальный сборщик метрик"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


@contextmanager
def measure_time(metric_name: str):
    """Контекстный менеджер для измерения времени"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        collector = get_metrics_collector()

        if metric_name == "validation":
            # Для валидации используем специальные методы
            pass  # Валидация сама записывает метрики
        elif metric_name == "api_request":
            collector.record_api_request(duration)
        elif metric_name == "okx_request":
            collector.record_okx_request(duration)
        elif metric_name == "cache_refresh":
            collector.metrics["cache_refresh_duration"].add_point(duration)


@asynccontextmanager
async def measure_async_time(metric_name: str):
    """Асинхронный контекстный менеджер для измерения времени"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        collector = get_metrics_collector()

        if metric_name == "validation":
            # Для валидации используем специальные методы
            pass
        elif metric_name == "api_request":
            collector.record_api_request(duration)
        elif metric_name == "okx_request":
            collector.record_okx_request(duration)
        elif metric_name == "cache_refresh":
            collector.metrics["cache_refresh_duration"].add_point(duration)


class MetricsExporter:
    """Экспортер метрик"""

    def __init__(self, port: int = 9090):
        self.config = get_config()
        self.port = port or self.config.metrics.metrics_port
        self.collector = get_metrics_collector()
        self._server = None
        self._enabled = self.config.metrics.export_metrics

    async def start_server(self):
        """Запускает HTTP сервер для экспорта метрик"""
        if not self._enabled:
            logger.info("Metrics export disabled in config")
            return

        try:
            from aiohttp import web

            async def metrics_handler(request):
                """Обработчик запроса метрик"""
                format = request.query.get("format", "json")

                try:
                    if format == "prometheus":
                        content_type = "text/plain"
                        content = self.collector.export_metrics("prometheus")
                    else:
                        content_type = "application/json"
                        content = self.collector.export_metrics("json")

                    return web.Response(text=content, content_type=content_type)
                except Exception as e:
                    logger.error(f"Error exporting metrics: {e}")
                    return web.Response(text=f"Error: {e!s}", status=500)

            async def health_handler(request):
                """Обработчик health check"""
                return web.Response(text="OK")

            app = web.Application()
            app.router.add_get("/metrics", metrics_handler)
            app.router.add_get("/health", health_handler)

            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, "localhost", self.port)
            await site.start()

            self._server = runner
            logger.info(f"Metrics server started on port {self.port}")

        except ImportError:
            logger.warning("aiohttp not installed, metrics server not started")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    async def stop_server(self):
        """Останавливает HTTP сервер"""
        if self._server:
            await self._server.cleanup()
            logger.info("Metrics server stopped")


class MetricsMonitor:
    """Монитор метрик с алертами"""

    def __init__(self):
        self.config = get_config()
        self.collector = get_metrics_collector()
        self.alerts: list[dict[str, Any]] = []
        self._monitoring_task: asyncio.Task | None = None
        self._enabled = self.config.metrics.enabled

    async def start_monitoring(self):
        """Запускает мониторинг метрик"""
        if not self._enabled:
            return

        if self._monitoring_task and not self._monitoring_task.done():
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Metrics monitoring started")

    async def stop_monitoring(self):
        """Останавливает мониторинг метрик"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitoring_task
            logger.info("Metrics monitoring stopped")

    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        while True:
            try:
                await self._check_alerts()
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics monitoring: {e}")
                await asyncio.sleep(60)  # Ждем дольше при ошибке

    async def _check_alerts(self):
        """Проверяет условия для алертов"""
        summary = self.collector.get_metrics_summary()

        # Проверяем cache hit ratio
        cache_hit = summary.get("cache_hit_ratio", {})
        if cache_hit.get("latest", 100) < 50:  # Меньше 50%
            await self._trigger_alert(
                "LOW_CACHE_HIT_RATIO",
                {
                    "metric": "cache_hit_ratio",
                    "value": cache_hit.get("latest"),
                    "threshold": 50,
                },
            )

        # Проверяем error rate
        error_rate = summary.get("error_rate", {})
        if error_rate.get("latest", 0) > 10:  # Больше 10%
            await self._trigger_alert(
                "HIGH_ERROR_RATE",
                {
                    "metric": "error_rate",
                    "value": error_rate.get("latest"),
                    "threshold": 10,
                },
            )

        # Проверяем API latency
        api_latency = summary.get("api_request_duration", {})
        if api_latency.get("latest", 0) > 5.0:  # Больше 5 секунд
            await self._trigger_alert(
                "HIGH_API_LATENCY",
                {
                    "metric": "api_request_duration",
                    "value": api_latency.get("latest"),
                    "threshold": 5.0,
                },
            )

    async def _trigger_alert(self, alert_type: str, context: dict[str, Any]):
        """Срабатывает алерт"""
        alert = {
            "type": alert_type,
            "timestamp": datetime.now().isoformat(),
            "context": context,
        }

        self.alerts.append(alert)
        logger.warning(f"Alert triggered: {alert_type} - {context}")

        # TODO: Интеграция с системой алертов (Slack, email, etc.)

    def get_alerts(self, hours: int = 24) -> list[dict[str, Any]]:
        """Возвращает алерты за последние N часов"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            alert
            for alert in self.alerts
            if datetime.fromisoformat(alert["timestamp"]) >= cutoff
        ]


# Глобальные экземпляры
_metrics_exporter: MetricsExporter | None = None
_metrics_monitor: MetricsMonitor | None = None


def get_metrics_exporter() -> MetricsExporter:
    """Возвращает глобальный экспортер метрик"""
    global _metrics_exporter
    if _metrics_exporter is None:
        _metrics_exporter = MetricsExporter()
    return _metrics_exporter


def get_metrics_monitor() -> MetricsMonitor:
    """Возвращает глобальный монитор метрик"""
    global _metrics_monitor
    if _metrics_monitor is None:
        _metrics_monitor = MetricsMonitor()
    return _metrics_monitor


async def start_metrics_services():
    """Запускает все сервисы метрик"""
    config = get_config()

    if not config.metrics.enabled:
        logger.info("Metrics disabled in config")
        return

    # Запускаем мониторинг
    monitor = get_metrics_monitor()
    await monitor.start_monitoring()

    # Запускаем экспортер если включен
    if config.metrics.export_metrics:
        exporter = get_metrics_exporter()
        await exporter.start_server()


async def stop_metrics_services():
    """Останавливает все сервисы метрик"""
    # Останавливаем мониторинг
    monitor = get_metrics_monitor()
    await monitor.stop_monitoring()

    # Останавливаем экспортер
    exporter = get_metrics_exporter()
    await exporter.stop_server()
