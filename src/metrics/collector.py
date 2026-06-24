"""
Сборщик метрик для мониторинга производительности и состояния системы.

DEPRECATED (G-12):  This is an in-memory metrics store with no Prometheus
integration.  No production code outside src/metrics/ imports from this module
(confirmed 2026-06-09).  This module is retained for test compatibility only
and will be removed once MetricsPort adapters replace its usages.

New code should use:
  - src/platform/ports.py MetricsPort  — abstract interface
  - src/candles/observability/prometheus.py  — candles push helpers
  - src/features/observability/prometheus.py — features push helpers
  - src/scoring_engine/observability.py       — scoring push helpers
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Типы метрик"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricValue:
    """Значение метрики"""

    value: float
    timestamp: datetime
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class Metric:
    """Метрика"""

    name: str
    type: MetricType
    description: str
    values: deque = field(default_factory=lambda: deque(maxlen=1000))
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Сборщик метрик"""

    def __init__(self, max_history: int = 1000):
        self.metrics: dict[str, Metric] = {}
        self.max_history = max_history
        self._lock = asyncio.Lock()

    async def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> None:
        """Регистрирует новую метрику"""
        async with self._lock:
            if name not in self.metrics:
                self.metrics[name] = Metric(
                    name=name,
                    type=metric_type,
                    description=description,
                    labels=labels or {},
                )
                logger.info(f"Зарегистрирована метрика: {name} ({metric_type.value})")

    async def increment_counter(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        """Увеличивает счетчик"""
        await self._add_metric_value(name, MetricType.COUNTER, value, labels)

    async def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Устанавливает значение gauge"""
        await self._add_metric_value(name, MetricType.GAUGE, value, labels)

    async def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Добавляет значение в гистограмму"""
        await self._add_metric_value(name, MetricType.HISTOGRAM, value, labels)

    async def observe_summary(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Добавляет значение в summary"""
        await self._add_metric_value(name, MetricType.SUMMARY, value, labels)

    async def _add_metric_value(
        self,
        name: str,
        metric_type: MetricType,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Добавляет значение метрики"""
        async with self._lock:
            if name not in self.metrics:
                await self.register_metric(name, metric_type, labels=labels or {})

            metric = self.metrics[name]
            metric_value = MetricValue(
                value=value, timestamp=datetime.utcnow(), labels=labels or {}
            )
            metric.values.append(metric_value)

    async def get_metric(self, name: str) -> Metric | None:
        """Получает метрику по имени"""
        async with self._lock:
            return self.metrics.get(name)

    async def get_all_metrics(self) -> dict[str, Metric]:
        """Получает все метрики"""
        async with self._lock:
            return self.metrics.copy()

    async def get_metric_summary(
        self, name: str, window_minutes: int = 5
    ) -> dict[str, Any] | None:
        """Получает сводку метрики за указанное время"""
        metric = await self.get_metric(name)
        if not metric:
            return None

        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_values = [mv for mv in metric.values if mv.timestamp >= cutoff_time]

        if not recent_values:
            return None

        values = [mv.value for mv in recent_values]

        summary = {
            "name": name,
            "type": metric.type.value,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "last_value": values[-1],
            "last_timestamp": recent_values[-1].timestamp,
        }

        if metric.type == MetricType.HISTOGRAM:
            summary["percentiles"] = {
                "50": self._percentile(values, 50),
                "90": self._percentile(values, 90),
                "95": self._percentile(values, 95),
                "99": self._percentile(values, 99),
            }

        return summary

    def _percentile(self, values: list[float], percentile: int) -> float:
        """Вычисляет перцентиль"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    async def clear_old_metrics(self, max_age_hours: int = 24) -> None:
        """Очищает старые метрики"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        async with self._lock:
            for metric in self.metrics.values():
                # Удаляем старые значения
                metric.values = deque(
                    [mv for mv in metric.values if mv.timestamp >= cutoff_time],
                    maxlen=self.max_history,
                )

        logger.info(f"Очищены метрики старше {max_age_hours} часов")


# Глобальный экземпляр сборщика метрик
metrics_collector = MetricsCollector()
