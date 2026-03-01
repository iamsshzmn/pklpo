"""
Тесты для системы метрик и мониторинга market_meta.
"""

import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.market_meta.infrastructure.metrics import (
    MetricPoint,
    MetricsCollector,
    MetricSeries,
    MetricsExporter,
    MetricsMonitor,
    get_metrics_collector,
    measure_async_time,
    measure_time,
    start_metrics_services,
    stop_metrics_services,
)


class TestMetricPoint:
    """Тесты точки метрики"""

    def test_metric_point_creation(self):
        """Тест создания точки метрики"""
        timestamp = datetime.now()
        point = MetricPoint(timestamp=timestamp, value=42.5, labels={"test": "value"})

        assert point.timestamp == timestamp
        assert point.value == 42.5
        assert point.labels == {"test": "value"}


class TestMetricSeries:
    """Тесты серии метрик"""

    def test_metric_series_creation(self):
        """Тест создания серии метрик"""
        series = MetricSeries("test_metric", "Test metric", "count")

        assert series.name == "test_metric"
        assert series.description == "Test metric"
        assert series.unit == "count"
        assert len(series.points) == 0

    def test_add_point(self):
        """Тест добавления точки метрики"""
        series = MetricSeries("test_metric", "Test metric", "count")

        series.add_point(42.5, {"label": "value"})

        assert len(series.points) == 1
        point = series.points[0]
        assert point.value == 42.5
        assert point.labels == {"label": "value"}

    def test_get_latest(self):
        """Тест получения последней точки"""
        series = MetricSeries("test_metric", "Test metric", "count")

        # Нет точек
        assert series.get_latest() is None

        # Добавляем точки
        series.add_point(10)
        series.add_point(20)

        latest = series.get_latest()
        assert latest.value == 20

    def test_get_average(self):
        """Тест получения среднего значения"""
        series = MetricSeries("test_metric", "Test metric", "count")

        # Нет точек
        assert series.get_average() is None

        # Добавляем точки
        series.add_point(10)
        series.add_point(20)
        series.add_point(30)

        average = series.get_average()
        assert average == 20.0

    def test_get_count(self):
        """Тест получения количества точек"""
        series = MetricSeries("test_metric", "Test metric", "count")

        # Нет точек
        assert series.get_count() == 0

        # Добавляем точки
        series.add_point(10)
        series.add_point(20)

        assert series.get_count() == 2


class TestMetricsCollector:
    """Тесты сборщика метрик"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        with patch(
            "src.market_meta.infrastructure.metrics.get_config"
        ) as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config
            self.collector = MetricsCollector()

    def test_init_metrics(self):
        """Тест инициализации метрик"""
        # Проверяем, что все базовые метрики созданы
        expected_metrics = [
            "cache_hit_ratio",
            "cache_miss_count",
            "cache_hit_count",
            "cache_refresh_duration",
            "validation_success_rate",
            "validation_failure_count",
            "validation_success_count",
            "validation_duration",
            "api_request_duration",
            "api_request_count",
            "api_error_count",
            "api_success_rate",
            "okx_request_duration",
            "okx_retry_count",
            "okx_rate_limit_hits",
            "okx_instruments_loaded",
            "memory_usage_mb",
            "active_connections",
            "error_rate",
        ]

        for metric_name in expected_metrics:
            assert metric_name in self.collector.metrics

    def test_record_cache_hit(self):
        """Тест записи cache hit"""
        self.collector.record_cache_hit()

        hit_metric = self.collector.metrics["cache_hit_count"]
        assert hit_metric.get_count() == 1

        ratio_metric = self.collector.metrics["cache_hit_ratio"]
        assert ratio_metric.get_latest().value == 100.0  # 100% hit rate

    def test_record_cache_miss(self):
        """Тест записи cache miss"""
        self.collector.record_cache_miss()

        miss_metric = self.collector.metrics["cache_miss_count"]
        assert miss_metric.get_count() == 1

        ratio_metric = self.collector.metrics["cache_hit_ratio"]
        assert ratio_metric.get_latest().value == 0.0  # 0% hit rate

    def test_record_validation_success(self):
        """Тест записи успешной валидации"""
        self.collector.record_validation_success(0.5)

        success_metric = self.collector.metrics["validation_success_count"]
        assert success_metric.get_count() == 1

        duration_metric = self.collector.metrics["validation_duration"]
        assert duration_metric.get_latest().value == 0.5

        rate_metric = self.collector.metrics["validation_success_rate"]
        assert rate_metric.get_latest().value == 100.0  # 100% success rate

    def test_record_validation_failure(self):
        """Тест записи неудачной валидации"""
        self.collector.record_validation_failure(0.3)

        failure_metric = self.collector.metrics["validation_failure_count"]
        assert failure_metric.get_count() == 1

        duration_metric = self.collector.metrics["validation_duration"]
        assert duration_metric.get_latest().value == 0.3

        rate_metric = self.collector.metrics["validation_success_rate"]
        assert rate_metric.get_latest().value == 0.0  # 0% success rate

    def test_record_api_request(self):
        """Тест записи API запроса"""
        self.collector.record_api_request(1.5, success=True)

        request_metric = self.collector.metrics["api_request_count"]
        assert request_metric.get_count() == 1

        duration_metric = self.collector.metrics["api_request_duration"]
        assert duration_metric.get_latest().value == 1.5

        success_metric = self.collector.metrics["api_success_rate"]
        assert success_metric.get_latest().value == 100.0  # 100% success rate

    def test_record_api_request_failure(self):
        """Тест записи неудачного API запроса"""
        self.collector.record_api_request(2.0, success=False)

        request_metric = self.collector.metrics["api_request_count"]
        assert request_metric.get_count() == 1

        error_metric = self.collector.metrics["api_error_count"]
        assert error_metric.get_count() == 1

        success_metric = self.collector.metrics["api_success_rate"]
        assert success_metric.get_latest().value == 0.0  # 0% success rate

    def test_record_okx_request(self):
        """Тест записи OKX запроса"""
        self.collector.record_okx_request(0.8, retries=2, rate_limited=True)

        duration_metric = self.collector.metrics["okx_request_duration"]
        assert duration_metric.get_latest().value == 0.8

        retry_metric = self.collector.metrics["okx_retry_count"]
        assert retry_metric.get_latest().value == 2

        rate_limit_metric = self.collector.metrics["okx_rate_limit_hits"]
        assert rate_limit_metric.get_latest().value == 1

    def test_record_instruments_loaded(self):
        """Тест записи количества загруженных инструментов"""
        self.collector.record_instruments_loaded(150)

        metric = self.collector.metrics["okx_instruments_loaded"]
        assert metric.get_latest().value == 150

    def test_get_metrics_summary(self):
        """Тест получения сводки метрик"""
        # Добавляем несколько метрик
        self.collector.record_cache_hit()
        self.collector.record_cache_miss()
        self.collector.record_validation_success(0.5)

        summary = self.collector.get_metrics_summary()

        # Проверяем структуру
        assert "cache_hit_ratio" in summary
        assert "validation_success_rate" in summary

        # Проверяем данные
        cache_hit = summary["cache_hit_ratio"]
        assert cache_hit["latest"] == 50.0  # 1 hit, 1 miss = 50%
        assert "latest_timestamp" in cache_hit
        assert "average_5m" in cache_hit
        assert "count_5m" in cache_hit
        assert "unit" in cache_hit
        assert "description" in cache_hit

    def test_export_metrics_json(self):
        """Тест экспорта метрик в JSON"""
        self.collector.record_cache_hit()

        json_output = self.collector.export_metrics("json")

        # Проверяем, что это валидный JSON
        import json

        data = json.loads(json_output)
        assert "cache_hit_ratio" in data

    def test_export_metrics_prometheus(self):
        """Тест экспорта метрик в Prometheus формате"""
        self.collector.record_cache_hit()

        prometheus_output = self.collector.export_metrics("prometheus")

        # Проверяем формат Prometheus
        lines = prometheus_output.split("\n")
        assert any(line.startswith("# HELP cache_hit_ratio") for line in lines)
        assert any(line.startswith("# TYPE cache_hit_ratio gauge") for line in lines)
        assert any(line.startswith("cache_hit_ratio") for line in lines)

    def test_export_metrics_invalid_format(self):
        """Тест экспорта метрик с неверным форматом"""
        with pytest.raises(ValueError, match="Unsupported format"):
            self.collector.export_metrics("invalid")


class TestMetricsContextManagers:
    """Тесты контекстных менеджеров для метрик"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        with patch(
            "src.market_meta.infrastructure.metrics.get_config"
        ) as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config
            self.collector = MetricsCollector()

    def test_measure_time_sync(self):
        """Тест синхронного контекстного менеджера"""
        from src.market_meta.infrastructure.metrics import get_metrics_collector

        collector = get_metrics_collector()
        with measure_time("api_request"):
            # Имитируем работу
            import time

            time.sleep(0.1)

        # Проверяем, что метрика записана
        metric = collector.metrics["api_request_duration"]
        assert metric.get_count() >= 1
        assert metric.get_latest().value > 0

    @pytest.mark.asyncio
    async def test_measure_async_time(self):
        """Тест асинхронного контекстного менеджера"""
        from src.market_meta.infrastructure.metrics import get_metrics_collector

        collector = get_metrics_collector()
        async with measure_async_time("okx_request"):
            # Имитируем асинхронную работу
            await asyncio.sleep(0.1)

        # Проверяем, что метрика записана
        metric = collector.metrics["okx_request_duration"]
        assert metric.get_count() >= 1
        assert metric.get_latest().value > 0


class TestMetricsExporter:
    """Тесты экспортера метрик"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        with patch(
            "src.market_meta.infrastructure.metrics.get_config"
        ) as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.export_metrics = True
            mock_config.metrics.metrics_port = 9090
            mock_get_config.return_value = mock_config
            self.exporter = MetricsExporter()

    @pytest.mark.asyncio
    async def test_start_server_no_aiohttp(self):
        """Тест запуска сервера без aiohttp"""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "aiohttp":
                raise ImportError("No module named 'aiohttp'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            await self.exporter.start_server()
            # Должен логировать предупреждение, но не падать

    @pytest.mark.asyncio
    async def test_stop_server(self):
        """Тест остановки сервера"""
        # Сервер не запущен
        await self.exporter.stop_server()
        # Не должно падать


class TestMetricsMonitor:
    """Тесты монитора метрик"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        with patch(
            "src.market_meta.infrastructure.metrics.get_config"
        ) as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config
            self.monitor = MetricsMonitor()

    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        """Тест запуска мониторинга"""
        await self.monitor.start_monitoring()

        # Проверяем, что задача создана
        assert self.monitor._monitoring_task is not None
        assert not self.monitor._monitoring_task.done()

        # Останавливаем
        await self.monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self):
        """Тест остановки мониторинга"""
        await self.monitor.start_monitoring()
        await self.monitor.stop_monitoring()

        # Проверяем, что задача отменена
        assert self.monitor._monitoring_task.cancelled()

    @pytest.mark.asyncio
    async def test_check_alerts(self):
        """Тест проверки алертов"""
        # Добавляем метрики, которые должны вызвать алерты
        self.monitor.collector.metrics["cache_hit_ratio"].add_point(
            30.0
        )  # Низкий hit ratio
        self.monitor.collector.metrics["error_rate"].add_point(
            15.0
        )  # Высокий error rate
        self.monitor.collector.metrics["api_request_duration"].add_point(
            6.0
        )  # Высокая латентность

        await self.monitor._check_alerts()

        # Проверяем, что алерты созданы
        assert len(self.monitor.alerts) >= 3

    def test_get_alerts(self):
        """Тест получения алертов"""
        # Добавляем тестовые алерты
        self.monitor.alerts = [
            {
                "type": "TEST_ALERT",
                "timestamp": datetime.now().isoformat(),
                "context": {"test": "value"},
            }
        ]

        alerts = self.monitor.get_alerts(hours=24)
        assert len(alerts) == 1
        assert alerts[0]["type"] == "TEST_ALERT"


class TestMetricsIntegration:
    """Интеграционные тесты метрик"""

    def test_get_metrics_collector_singleton(self):
        """Тест синглтона сборщика метрик"""
        with patch(
            "src.market_meta.infrastructure.metrics.get_config"
        ) as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config

            # Сбрасываем глобальный экземпляр
            import src.market_meta.infrastructure.metrics as metrics_module

            metrics_module._metrics_collector = None

            collector1 = get_metrics_collector()
            collector2 = get_metrics_collector()

            assert collector1 is collector2

    @pytest.mark.asyncio
    async def test_start_stop_metrics_services(self):
        """Тест запуска и остановки сервисов метрик"""
        with patch(
            "src.market_meta.infrastructure.metrics.get_config"
        ) as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_config.metrics.export_metrics = False
            mock_get_config.return_value = mock_config

            # Запускаем сервисы
            await start_metrics_services()

            # Останавливаем сервисы
            await stop_metrics_services()

            # Не должно падать


if __name__ == "__main__":
    pytest.main([__file__])
