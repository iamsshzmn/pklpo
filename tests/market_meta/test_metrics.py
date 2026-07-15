"""
РўРµСЃС‚С‹ РґР»СЏ СЃРёСЃС‚РµРјС‹ РјРµС‚СЂРёРє Рё РјРѕРЅРёС‚РѕСЂРёРЅРіР° market_meta.
"""

import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.market_meta_backup.infrastructure.metrics import (
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
    """РўРµСЃС‚С‹ С‚РѕС‡РєРё РјРµС‚СЂРёРєРё"""

    def test_metric_point_creation(self):
        """РўРµСЃС‚ СЃРѕР·РґР°РЅРёСЏ С‚РѕС‡РєРё РјРµС‚СЂРёРєРё"""
        timestamp = datetime.now()
        point = MetricPoint(timestamp=timestamp, value=42.5, labels={"test": "value"})

        assert point.timestamp == timestamp
        assert point.value == 42.5
        assert point.labels == {"test": "value"}


class TestMetricSeries:
    """РўРµСЃС‚С‹ СЃРµСЂРёРё РјРµС‚СЂРёРє"""

    def test_metric_series_creation(self):
        """РўРµСЃС‚ СЃРѕР·РґР°РЅРёСЏ СЃРµСЂРёРё РјРµС‚СЂРёРє"""
        series = MetricSeries("test_metric", "Test metric", "count")

        assert series.name == "test_metric"
        assert series.description == "Test metric"
        assert series.unit == "count"
        assert len(series.points) == 0

    def test_add_point(self):
        """РўРµСЃС‚ РґРѕР±Р°РІР»РµРЅРёСЏ С‚РѕС‡РєРё РјРµС‚СЂРёРєРё"""
        series = MetricSeries("test_metric", "Test metric", "count")

        series.add_point(42.5, {"label": "value"})

        assert len(series.points) == 1
        point = series.points[0]
        assert point.value == 42.5
        assert point.labels == {"label": "value"}

    def test_get_latest(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РїРѕСЃР»РµРґРЅРµР№ С‚РѕС‡РєРё"""
        series = MetricSeries("test_metric", "Test metric", "count")

        # РќРµС‚ С‚РѕС‡РµРє
        assert series.get_latest() is None

        # Р”РѕР±Р°РІР»СЏРµРј С‚РѕС‡РєРё
        series.add_point(10)
        series.add_point(20)

        latest = series.get_latest()
        assert latest.value == 20

    def test_get_average(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ СЃСЂРµРґРЅРµРіРѕ Р·РЅР°С‡РµРЅРёСЏ"""
        series = MetricSeries("test_metric", "Test metric", "count")

        # РќРµС‚ С‚РѕС‡РµРє
        assert series.get_average() is None

        # Р”РѕР±Р°РІР»СЏРµРј С‚РѕС‡РєРё
        series.add_point(10)
        series.add_point(20)
        series.add_point(30)

        average = series.get_average()
        assert average == 20.0

    def test_get_count(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ РєРѕР»РёС‡РµСЃС‚РІР° С‚РѕС‡РµРє"""
        series = MetricSeries("test_metric", "Test metric", "count")

        # РќРµС‚ С‚РѕС‡РµРє
        assert series.get_count() == 0

        # Р”РѕР±Р°РІР»СЏРµРј С‚РѕС‡РєРё
        series.add_point(10)
        series.add_point(20)

        assert series.get_count() == 2


class TestMetricsCollector:
    """РўРµСЃС‚С‹ СЃР±РѕСЂС‰РёРєР° РјРµС‚СЂРёРє"""

    def setup_method(self):
        """РќР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРґ РєР°Р¶РґС‹Рј С‚РµСЃС‚РѕРј"""
        with patch("src.candles.infrastructure.metrics.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config
            self.collector = MetricsCollector()

    def test_init_metrics(self):
        """РўРµСЃС‚ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё РјРµС‚СЂРёРє"""
        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РІСЃРµ Р±Р°Р·РѕРІС‹Рµ РјРµС‚СЂРёРєРё СЃРѕР·РґР°РЅС‹
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
        """РўРµСЃС‚ Р·Р°РїРёСЃРё cache hit"""
        self.collector.record_cache_hit()

        hit_metric = self.collector.metrics["cache_hit_count"]
        assert hit_metric.get_count() == 1

        ratio_metric = self.collector.metrics["cache_hit_ratio"]
        assert ratio_metric.get_latest().value == 100.0  # 100% hit rate

    def test_record_cache_miss(self):
        """РўРµСЃС‚ Р·Р°РїРёСЃРё cache miss"""
        self.collector.record_cache_miss()

        miss_metric = self.collector.metrics["cache_miss_count"]
        assert miss_metric.get_count() == 1

        ratio_metric = self.collector.metrics["cache_hit_ratio"]
        assert ratio_metric.get_latest().value == 0.0  # 0% hit rate

    def test_record_validation_success(self):
        """РўРµСЃС‚ Р·Р°РїРёСЃРё СѓСЃРїРµС€РЅРѕР№ РІР°Р»РёРґР°С†РёРё"""
        self.collector.record_validation_success(0.5)

        success_metric = self.collector.metrics["validation_success_count"]
        assert success_metric.get_count() == 1

        duration_metric = self.collector.metrics["validation_duration"]
        assert duration_metric.get_latest().value == 0.5

        rate_metric = self.collector.metrics["validation_success_rate"]
        assert rate_metric.get_latest().value == 100.0  # 100% success rate

    def test_record_validation_failure(self):
        """РўРµСЃС‚ Р·Р°РїРёСЃРё РЅРµСѓРґР°С‡РЅРѕР№ РІР°Р»РёРґР°С†РёРё"""
        self.collector.record_validation_failure(0.3)

        failure_metric = self.collector.metrics["validation_failure_count"]
        assert failure_metric.get_count() == 1

        duration_metric = self.collector.metrics["validation_duration"]
        assert duration_metric.get_latest().value == 0.3

        rate_metric = self.collector.metrics["validation_success_rate"]
        assert rate_metric.get_latest().value == 0.0  # 0% success rate

    def test_record_api_request(self):
        """РўРµСЃС‚ Р·Р°РїРёСЃРё API Р·Р°РїСЂРѕСЃР°"""
        self.collector.record_api_request(1.5, success=True)

        request_metric = self.collector.metrics["api_request_count"]
        assert request_metric.get_count() == 1

        duration_metric = self.collector.metrics["api_request_duration"]
        assert duration_metric.get_latest().value == 1.5

        success_metric = self.collector.metrics["api_success_rate"]
        assert success_metric.get_latest().value == 100.0  # 100% success rate

    def test_record_api_request_failure(self):
        """РўРµСЃС‚ Р·Р°РїРёСЃРё РЅРµСѓРґР°С‡РЅРѕРіРѕ API Р·Р°РїСЂРѕСЃР°"""
        self.collector.record_api_request(2.0, success=False)

        request_metric = self.collector.metrics["api_request_count"]
        assert request_metric.get_count() == 1

        error_metric = self.collector.metrics["api_error_count"]
        assert error_metric.get_count() == 1

        success_metric = self.collector.metrics["api_success_rate"]
        assert success_metric.get_latest().value == 0.0  # 0% success rate

    def test_record_okx_request(self):
        """РўРµСЃС‚ Р·Р°РїРёСЃРё OKX Р·Р°РїСЂРѕСЃР°"""
        self.collector.record_okx_request(0.8, retries=2, rate_limited=True)

        duration_metric = self.collector.metrics["okx_request_duration"]
        assert duration_metric.get_latest().value == 0.8

        retry_metric = self.collector.metrics["okx_retry_count"]
        assert retry_metric.get_latest().value == 2

        rate_limit_metric = self.collector.metrics["okx_rate_limit_hits"]
        assert rate_limit_metric.get_latest().value == 1

    def test_record_instruments_loaded(self):
        """РўРµСЃС‚ Р·Р°РїРёСЃРё РєРѕР»РёС‡РµСЃС‚РІР° Р·Р°РіСЂСѓР¶РµРЅРЅС‹С… РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ"""
        self.collector.record_instruments_loaded(150)

        metric = self.collector.metrics["okx_instruments_loaded"]
        assert metric.get_latest().value == 150

    def test_get_metrics_summary(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ СЃРІРѕРґРєРё РјРµС‚СЂРёРє"""
        # Р”РѕР±Р°РІР»СЏРµРј РЅРµСЃРєРѕР»СЊРєРѕ РјРµС‚СЂРёРє
        self.collector.record_cache_hit()
        self.collector.record_cache_miss()
        self.collector.record_validation_success(0.5)

        summary = self.collector.get_metrics_summary()

        # РџСЂРѕРІРµСЂСЏРµРј СЃС‚СЂСѓРєС‚СѓСЂСѓ
        assert "cache_hit_ratio" in summary
        assert "validation_success_rate" in summary

        # РџСЂРѕРІРµСЂСЏРµРј РґР°РЅРЅС‹Рµ
        cache_hit = summary["cache_hit_ratio"]
        assert cache_hit["latest"] == 50.0  # 1 hit, 1 miss = 50%
        assert "latest_timestamp" in cache_hit
        assert "average_5m" in cache_hit
        assert "count_5m" in cache_hit
        assert "unit" in cache_hit
        assert "description" in cache_hit

    def test_export_metrics_json(self):
        """РўРµСЃС‚ СЌРєСЃРїРѕСЂС‚Р° РјРµС‚СЂРёРє РІ JSON"""
        self.collector.record_cache_hit()

        json_output = self.collector.export_metrics("json")

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ СЌС‚Рѕ РІР°Р»РёРґРЅС‹Р№ JSON
        import json

        data = json.loads(json_output)
        assert "cache_hit_ratio" in data

    def test_export_metrics_prometheus(self):
        """РўРµСЃС‚ СЌРєСЃРїРѕСЂС‚Р° РјРµС‚СЂРёРє РІ Prometheus С„РѕСЂРјР°С‚Рµ"""
        self.collector.record_cache_hit()

        prometheus_output = self.collector.export_metrics("prometheus")

        # РџСЂРѕРІРµСЂСЏРµРј С„РѕСЂРјР°С‚ Prometheus
        lines = prometheus_output.split("\n")
        assert any(line.startswith("# HELP cache_hit_ratio") for line in lines)
        assert any(line.startswith("# TYPE cache_hit_ratio gauge") for line in lines)
        assert any(line.startswith("cache_hit_ratio") for line in lines)

    def test_export_metrics_invalid_format(self):
        """РўРµСЃС‚ СЌРєСЃРїРѕСЂС‚Р° РјРµС‚СЂРёРє СЃ РЅРµРІРµСЂРЅС‹Рј С„РѕСЂРјР°С‚РѕРј"""
        with pytest.raises(ValueError, match="Unsupported format"):
            self.collector.export_metrics("invalid")


class TestMetricsContextManagers:
    """РўРµСЃС‚С‹ РєРѕРЅС‚РµРєСЃС‚РЅС‹С… РјРµРЅРµРґР¶РµСЂРѕРІ РґР»СЏ РјРµС‚СЂРёРє"""

    def setup_method(self):
        """РќР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРґ РєР°Р¶РґС‹Рј С‚РµСЃС‚РѕРј"""
        with patch("src.candles.infrastructure.metrics.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config
            self.collector = MetricsCollector()

    def test_measure_time_sync(self):
        """РўРµСЃС‚ СЃРёРЅС…СЂРѕРЅРЅРѕРіРѕ РєРѕРЅС‚РµРєСЃС‚РЅРѕРіРѕ РјРµРЅРµРґР¶РµСЂР°"""
        from src.market_meta_backup.infrastructure.metrics import get_metrics_collector

        collector = get_metrics_collector()
        with measure_time("api_request"):
            # РРјРёС‚РёСЂСѓРµРј СЂР°Р±РѕС‚Сѓ
            import time

            time.sleep(0.1)

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РјРµС‚СЂРёРєР° Р·Р°РїРёСЃР°РЅР°
        metric = collector.metrics["api_request_duration"]
        assert metric.get_count() >= 1
        assert metric.get_latest().value > 0

    @pytest.mark.asyncio
    async def test_measure_async_time(self):
        """РўРµСЃС‚ Р°СЃРёРЅС…СЂРѕРЅРЅРѕРіРѕ РєРѕРЅС‚РµРєСЃС‚РЅРѕРіРѕ РјРµРЅРµРґР¶РµСЂР°"""
        from src.market_meta_backup.infrastructure.metrics import get_metrics_collector

        collector = get_metrics_collector()
        async with measure_async_time("okx_request"):
            # РРјРёС‚РёСЂСѓРµРј Р°СЃРёРЅС…СЂРѕРЅРЅСѓСЋ СЂР°Р±РѕС‚Сѓ
            await asyncio.sleep(0.1)

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ РјРµС‚СЂРёРєР° Р·Р°РїРёСЃР°РЅР°
        metric = collector.metrics["okx_request_duration"]
        assert metric.get_count() >= 1
        assert metric.get_latest().value > 0


class TestMetricsExporter:
    """РўРµСЃС‚С‹ СЌРєСЃРїРѕСЂС‚РµСЂР° РјРµС‚СЂРёРє"""

    def setup_method(self):
        """РќР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРґ РєР°Р¶РґС‹Рј С‚РµСЃС‚РѕРј"""
        with patch("src.candles.infrastructure.metrics.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.export_metrics = True
            mock_config.metrics.metrics_port = 9090
            mock_get_config.return_value = mock_config
            self.exporter = MetricsExporter()

    @pytest.mark.asyncio
    async def test_start_server_no_aiohttp(self):
        """РўРµСЃС‚ Р·Р°РїСѓСЃРєР° СЃРµСЂРІРµСЂР° Р±РµР· aiohttp"""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "aiohttp":
                raise ImportError("No module named 'aiohttp'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            await self.exporter.start_server()
            # Р”РѕР»Р¶РµРЅ Р»РѕРіРёСЂРѕРІР°С‚СЊ РїСЂРµРґСѓРїСЂРµР¶РґРµРЅРёРµ, РЅРѕ РЅРµ РїР°РґР°С‚СЊ

    @pytest.mark.asyncio
    async def test_stop_server(self):
        """РўРµСЃС‚ РѕСЃС‚Р°РЅРѕРІРєРё СЃРµСЂРІРµСЂР°"""
        # РЎРµСЂРІРµСЂ РЅРµ Р·Р°РїСѓС‰РµРЅ
        await self.exporter.stop_server()
        # РќРµ РґРѕР»Р¶РЅРѕ РїР°РґР°С‚СЊ


class TestMetricsMonitor:
    """РўРµСЃС‚С‹ РјРѕРЅРёС‚РѕСЂР° РјРµС‚СЂРёРє"""

    def setup_method(self):
        """РќР°СЃС‚СЂРѕР№РєР° РїРµСЂРµРґ РєР°Р¶РґС‹Рј С‚РµСЃС‚РѕРј"""
        with patch("src.candles.infrastructure.metrics.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config
            self.monitor = MetricsMonitor()

    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        """РўРµСЃС‚ Р·Р°РїСѓСЃРєР° РјРѕРЅРёС‚РѕСЂРёРЅРіР°"""
        await self.monitor.start_monitoring()

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ Р·Р°РґР°С‡Р° СЃРѕР·РґР°РЅР°
        assert self.monitor._monitoring_task is not None
        assert not self.monitor._monitoring_task.done()

        # РћСЃС‚Р°РЅР°РІР»РёРІР°РµРј
        await self.monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self):
        """РўРµСЃС‚ РѕСЃС‚Р°РЅРѕРІРєРё РјРѕРЅРёС‚РѕСЂРёРЅРіР°"""
        await self.monitor.start_monitoring()
        await self.monitor.stop_monitoring()

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ Р·Р°РґР°С‡Р° РѕС‚РјРµРЅРµРЅР°
        assert self.monitor._monitoring_task.cancelled()

    @pytest.mark.asyncio
    async def test_check_alerts(self):
        """РўРµСЃС‚ РїСЂРѕРІРµСЂРєРё Р°Р»РµСЂС‚РѕРІ"""
        # Р”РѕР±Р°РІР»СЏРµРј РјРµС‚СЂРёРєРё, РєРѕС‚РѕСЂС‹Рµ РґРѕР»Р¶РЅС‹ РІС‹Р·РІР°С‚СЊ Р°Р»РµСЂС‚С‹
        self.monitor.collector.metrics["cache_hit_ratio"].add_point(
            30.0
        )  # РќРёР·РєРёР№ hit ratio
        self.monitor.collector.metrics["error_rate"].add_point(
            15.0
        )  # Р’С‹СЃРѕРєРёР№ error rate
        self.monitor.collector.metrics["api_request_duration"].add_point(
            6.0
        )  # Р’С‹СЃРѕРєР°СЏ Р»Р°С‚РµРЅС‚РЅРѕСЃС‚СЊ

        await self.monitor._check_alerts()

        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ Р°Р»РµСЂС‚С‹ СЃРѕР·РґР°РЅС‹
        assert len(self.monitor.alerts) >= 3

    def test_get_alerts(self):
        """РўРµСЃС‚ РїРѕР»СѓС‡РµРЅРёСЏ Р°Р»РµСЂС‚РѕРІ"""
        # Р”РѕР±Р°РІР»СЏРµРј С‚РµСЃС‚РѕРІС‹Рµ Р°Р»РµСЂС‚С‹
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
    """РРЅС‚РµРіСЂР°С†РёРѕРЅРЅС‹Рµ С‚РµСЃС‚С‹ РјРµС‚СЂРёРє"""

    def test_get_metrics_collector_singleton(self):
        """РўРµСЃС‚ СЃРёРЅРіР»С‚РѕРЅР° СЃР±РѕСЂС‰РёРєР° РјРµС‚СЂРёРє"""
        with patch("src.candles.infrastructure.metrics.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_get_config.return_value = mock_config

            # РЎР±СЂР°СЃС‹РІР°РµРј РіР»РѕР±Р°Р»СЊРЅС‹Р№ СЌРєР·РµРјРїР»СЏСЂ
            import src.candles.infrastructure.metrics as metrics_module

            metrics_module._metrics_collector = None

            collector1 = get_metrics_collector()
            collector2 = get_metrics_collector()

            assert collector1 is collector2

    @pytest.mark.asyncio
    async def test_start_stop_metrics_services(self):
        """РўРµСЃС‚ Р·Р°РїСѓСЃРєР° Рё РѕСЃС‚Р°РЅРѕРІРєРё СЃРµСЂРІРёСЃРѕРІ РјРµС‚СЂРёРє"""
        with patch("src.candles.infrastructure.metrics.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.metrics.enabled = True
            mock_config.metrics.export_metrics = False
            mock_get_config.return_value = mock_config

            # Р—Р°РїСѓСЃРєР°РµРј СЃРµСЂРІРёСЃС‹
            await start_metrics_services()

            # РћСЃС‚Р°РЅР°РІР»РёРІР°РµРј СЃРµСЂРІРёСЃС‹
            await stop_metrics_services()

            # РќРµ РґРѕР»Р¶РЅРѕ РїР°РґР°С‚СЊ


if __name__ == "__main__":
    pytest.main([__file__])
