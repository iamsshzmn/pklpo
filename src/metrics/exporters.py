"""
Экспортеры метрик для различных систем мониторинга
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .collector import MetricsCollector, MetricType, metrics_collector

logger = logging.getLogger(__name__)


class MetricsExporter(ABC):
    """Базовый класс для экспортеров метрик"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    @abstractmethod
    async def export_metrics(self) -> str:
        """Экспортирует метрики в определенном формате"""
        pass


class ConsoleExporter(MetricsExporter):
    """Экспортер метрик в консоль"""

    async def export_metrics(self) -> str:
        """Экспортирует метрики в читаемом формате для консоли"""
        metrics = await self.collector.get_all_metrics()

        if not metrics:
            return "📊 Метрики не найдены"

        output = []
        output.append("📊 МЕТРИКИ СИСТЕМЫ")
        output.append("=" * 60)

        for name, metric in metrics.items():
            if not metric.values:
                continue

            latest_value = metric.values[-1]
            output.append(f"\n🔹 {name} ({metric.type.value})")
            output.append(f"   Описание: {metric.description or 'Нет описания'}")
            output.append(f"   Последнее значение: {latest_value.value}")
            output.append(f"   Время: {latest_value.timestamp.strftime('%H:%M:%S')}")

            # Добавляем сводку за последние 5 минут
            summary = await self.collector.get_metric_summary(name, 5)
            if summary:
                output.append("   Сводка (5 мин):")
                output.append(f"     Количество: {summary['count']}")
                output.append(f"     Среднее: {summary['avg']:.2f}")
                output.append(
                    f"     Мин/Макс: {summary['min']:.2f}/{summary['max']:.2f}"
                )

                if metric.type == MetricType.HISTOGRAM and "percentiles" in summary:
                    output.append(f"     P95: {summary['percentiles']['95']:.2f}")
                    output.append(f"     P99: {summary['percentiles']['99']:.2f}")

        return "\n".join(output)

    async def export_system_health(self, health_data: dict[str, Any]) -> str:
        """Экспортирует состояние здоровья системы"""
        output = []
        output.append("🏥 СОСТОЯНИЕ ЗДОРОВЬЯ СИСТЕМЫ")
        output.append("=" * 60)
        output.append(
            f"Время: {health_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        output.append(f"Статус: {health_data['overall_status'].upper()}")

        if health_data["warnings"]:
            output.append("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
            for warning in health_data["warnings"]:
                output.append(f"  • {warning}")

        if health_data["critical_issues"]:
            output.append("\n🚨 КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
            for issue in health_data["critical_issues"]:
                output.append(f"  • {issue}")

        if not health_data["warnings"] and not health_data["critical_issues"]:
            output.append("\n✅ Система работает нормально")

        return "\n".join(output)


class PrometheusExporter(MetricsExporter):
    """Экспортер метрик в формате Prometheus"""

    async def export_metrics(self) -> str:
        """Экспортирует метрики в формате Prometheus"""
        metrics = await self.collector.get_all_metrics()

        if not metrics:
            return "# No metrics available"

        output = []

        for name, metric in metrics.items():
            if not metric.values:
                continue

            # Добавляем описание метрики
            if metric.description:
                output.append(f"# HELP {name} {metric.description}")
                output.append(f"# TYPE {name} {metric.type.value}")

            # Получаем последнее значение
            latest_value = metric.values[-1]

            # Формируем labels
            labels_str = ""
            if latest_value.labels:
                labels_parts = [f'{k}="{v}"' for k, v in latest_value.labels.items()]
                labels_str = "{" + ",".join(labels_parts) + "}"

            # Формируем строку метрики
            metric_line = f"{name}{labels_str} {latest_value.value}"

            # Добавляем timestamp в миллисекундах
            timestamp_ms = int(latest_value.timestamp.timestamp() * 1000)
            metric_line += f" {timestamp_ms}"

            output.append(metric_line)

        return "\n".join(output)


class JSONExporter(MetricsExporter):
    """Экспортер метрик в формате JSON"""

    async def export_metrics(self) -> str:
        """Экспортирует метрики в формате JSON"""
        metrics = await self.collector.get_all_metrics()

        if not metrics:
            return json.dumps({"metrics": []})

        metrics_data = []

        for name, metric in metrics.items():
            if not metric.values:
                continue

            metric_data = {
                "name": name,
                "type": metric.type.value,
                "description": metric.description,
                "labels": metric.labels,
                "values": [],
            }

            # Добавляем последние 10 значений
            for value in list(metric.values)[-10:]:
                metric_data["values"].append(
                    {
                        "value": value.value,
                        "timestamp": value.timestamp.isoformat(),
                        "labels": value.labels,
                    }
                )

            metrics_data.append(metric_data)

        return json.dumps(
            {"timestamp": datetime.utcnow().isoformat(), "metrics": metrics_data},
            indent=2,
        )


class MetricsDashboard:
    """Простая панель мониторинга метрик"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self.console_exporter = ConsoleExporter(collector)

    async def show_dashboard(self) -> str:
        """Показывает панель мониторинга"""
        output = []
        output.append("📊 ПАНЕЛЬ МОНИТОРИНГА")
        output.append("=" * 80)
        output.append(f"Время: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

        # Системные метрики
        system_metrics = await self._get_system_metrics()
        if system_metrics:
            output.append("\n🖥️  СИСТЕМНЫЕ МЕТРИКИ:")
            output.append("-" * 40)
            for metric_name, value in system_metrics.items():
                output.append(f"  {metric_name}: {value}")

        # Метрики процесса
        process_metrics = await self._get_process_metrics()
        if process_metrics:
            output.append("\n⚙️  МЕТРИКИ ПРОЦЕССА:")
            output.append("-" * 40)
            for metric_name, value in process_metrics.items():
                output.append(f"  {metric_name}: {value}")

        # Метрики базы данных
        db_metrics = await self._get_database_metrics()
        if db_metrics:
            output.append("\n🗄️  МЕТРИКИ БАЗЫ ДАННЫХ:")
            output.append("-" * 40)
            for metric_name, value in db_metrics.items():
                output.append(f"  {metric_name}: {value}")

        # Пользовательские метрики
        custom_metrics = await self._get_custom_metrics()
        if custom_metrics:
            output.append("\n📈 ПОЛЬЗОВАТЕЛЬСКИЕ МЕТРИКИ:")
            output.append("-" * 40)
            for metric_name, value in custom_metrics.items():
                output.append(f"  {metric_name}: {value}")

        return "\n".join(output)

    async def _get_system_metrics(self) -> dict[str, str]:
        """Получает системные метрики"""
        system_metric_names = [
            "system_cpu_percent",
            "system_memory_percent",
            "system_disk_usage_percent",
        ]

        metrics = {}
        for name in system_metric_names:
            summary = await self.collector.get_metric_summary(name, 5)
            if summary:
                metrics[name] = f"{summary['last_value']:.1f}%"

        return metrics

    async def _get_process_metrics(self) -> dict[str, str]:
        """Получает метрики процесса"""
        process_metric_names = [
            "process_cpu_percent",
            "process_memory_mb",
            "process_threads",
        ]

        metrics = {}
        for name in process_metric_names:
            summary = await self.collector.get_metric_summary(name, 5)
            if summary:
                if "mb" in name:
                    metrics[name] = f"{summary['last_value']:.1f} MB"
                else:
                    metrics[name] = f"{summary['last_value']:.1f}"

        return metrics

    async def _get_database_metrics(self) -> dict[str, str]:
        """Получает метрики базы данных"""
        db_metric_names = ["database_table_records", "database_table_size_mb"]

        metrics = {}
        for name in db_metric_names:
            summary = await self.collector.get_metric_summary(name, 5)
            if summary:
                if "size" in name:
                    metrics[name] = f"{summary['last_value']:.1f} MB"
                else:
                    metrics[name] = f"{summary['last_value']:.0f}"

        return metrics

    async def _get_custom_metrics(self) -> dict[str, str]:
        """Получает пользовательские метрики"""
        all_metrics = await self.collector.get_all_metrics()

        # Исключаем системные, процессные и БД метрики
        excluded_prefixes = ["system_", "process_", "database_"]

        custom_metrics = {}
        for name, metric in all_metrics.items():
            if not any(name.startswith(prefix) for prefix in excluded_prefixes):
                if metric.values:
                    latest_value = metric.values[-1]
                    custom_metrics[name] = f"{latest_value.value:.2f}"

        return custom_metrics


# Глобальные экземпляры экспортеров
console_exporter = ConsoleExporter(metrics_collector)
prometheus_exporter = PrometheusExporter(metrics_collector)
json_exporter = JSONExporter(metrics_collector)
metrics_dashboard = MetricsDashboard(metrics_collector)
