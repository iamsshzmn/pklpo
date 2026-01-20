"""
Декораторы для автоматического отслеживания метрик
"""

import asyncio
import functools
import logging
import time
from collections.abc import Callable

from .collector import MetricType, metrics_collector

logger = logging.getLogger(__name__)


def track_metrics(
    metric_name: str,
    metric_type: MetricType = MetricType.COUNTER,
    description: str = "",
    labels: dict[str, str] | None = None,
):
    """
    Декоратор для отслеживания вызовов функций

    Args:
        metric_name: Имя метрики
        metric_type: Тип метрики
        description: Описание метрики
        labels: Дополнительные метки
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                # Увеличиваем счетчик вызовов
                await metrics_collector.increment_counter(
                    f"{metric_name}_calls_total", labels=labels
                )

                result = await func(*args, **kwargs)

                # Увеличиваем счетчик успешных вызовов
                await metrics_collector.increment_counter(
                    f"{metric_name}_success_total", labels=labels
                )

                return result

            except Exception:
                # Увеличиваем счетчик ошибок
                await metrics_collector.increment_counter(
                    f"{metric_name}_errors_total", labels=labels
                )
                raise
            finally:
                # Записываем время выполнения
                execution_time = time.time() - start_time
                await metrics_collector.observe_histogram(
                    f"{metric_name}_duration_seconds", execution_time, labels=labels
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                # Увеличиваем счетчик вызовов
                asyncio.create_task(
                    metrics_collector.increment_counter(
                        f"{metric_name}_calls_total", labels=labels
                    )
                )

                result = func(*args, **kwargs)

                # Увеличиваем счетчик успешных вызовов
                asyncio.create_task(
                    metrics_collector.increment_counter(
                        f"{metric_name}_success_total", labels=labels
                    )
                )

                return result

            except Exception:
                # Увеличиваем счетчик ошибок
                asyncio.create_task(
                    metrics_collector.increment_counter(
                        f"{metric_name}_errors_total", labels=labels
                    )
                )
                raise
            finally:
                # Записываем время выполнения
                execution_time = time.time() - start_time
                asyncio.create_task(
                    metrics_collector.observe_histogram(
                        f"{metric_name}_duration_seconds", execution_time, labels=labels
                    )
                )

        # Определяем, является ли функция асинхронной
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_performance(
    metric_name: str, description: str = "", labels: dict[str, str] | None = None
):
    """
    Декоратор для отслеживания производительности функций

    Args:
        metric_name: Имя метрики
        description: Описание метрики
        labels: Дополнительные метки
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                execution_time = time.time() - start_time
                await metrics_collector.observe_histogram(
                    f"{metric_name}_duration_seconds", execution_time, labels=labels
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                execution_time = time.time() - start_time
                asyncio.create_task(
                    metrics_collector.observe_histogram(
                        f"{metric_name}_duration_seconds", execution_time, labels=labels
                    )
                )

        # Определяем, является ли функция асинхронной
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_database_operations(
    operation_type: str, table_name: str | None = None, description: str = ""
):
    """
    Декоратор для отслеживания операций с базой данных

    Args:
        operation_type: Тип операции (select, insert, update, delete)
        table_name: Имя таблицы
        description: Описание операции
        labels: Дополнительные метки
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            labels = {"operation": operation_type}
            if table_name:
                labels["table"] = table_name

            try:
                result = await func(*args, **kwargs)

                # Увеличиваем счетчик успешных операций
                await metrics_collector.increment_counter(
                    "database_operations_total", labels=labels
                )

                return result

            except Exception:
                # Увеличиваем счетчик ошибок
                await metrics_collector.increment_counter(
                    "database_errors_total", labels=labels
                )
                raise
            finally:
                # Записываем время выполнения
                execution_time = time.time() - start_time
                await metrics_collector.observe_histogram(
                    "database_operation_duration_seconds",
                    execution_time,
                    labels=labels,
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            labels = {"operation": operation_type}
            if table_name:
                labels["table"] = table_name

            try:
                result = func(*args, **kwargs)

                # Увеличиваем счетчик успешных операций
                asyncio.create_task(
                    metrics_collector.increment_counter(
                        "database_operations_total", labels=labels
                    )
                )

                return result

            except Exception:
                # Увеличиваем счетчик ошибок
                asyncio.create_task(
                    metrics_collector.increment_counter(
                        "database_errors_total", labels=labels
                    )
                )
                raise
            finally:
                # Записываем время выполнения
                execution_time = time.time() - start_time
                asyncio.create_task(
                    metrics_collector.observe_histogram(
                        "database_operation_duration_seconds",
                        execution_time,
                        labels=labels,
                    )
                )

        # Определяем, является ли функция асинхронной
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_api_calls(endpoint: str, method: str = "GET", description: str = ""):
    """
    Декоратор для отслеживания API вызовов

    Args:
        endpoint: Эндпоинт API
        method: HTTP метод
        description: Описание эндпоинта
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            labels = {"endpoint": endpoint, "method": method}

            try:
                result = await func(*args, **kwargs)

                # Увеличиваем счетчик успешных вызовов
                await metrics_collector.increment_counter(
                    "api_calls_total", labels=labels
                )

                return result

            except Exception:
                # Увеличиваем счетчик ошибок
                await metrics_collector.increment_counter(
                    "api_errors_total", labels=labels
                )
                raise
            finally:
                # Записываем время выполнения
                execution_time = time.time() - start_time
                await metrics_collector.observe_histogram(
                    "api_call_duration_seconds", execution_time, labels=labels
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            labels = {"endpoint": endpoint, "method": method}

            try:
                result = func(*args, **kwargs)

                # Увеличиваем счетчик успешных вызовов
                asyncio.create_task(
                    metrics_collector.increment_counter(
                        "api_calls_total", labels=labels
                    )
                )

                return result

            except Exception:
                # Увеличиваем счетчик ошибок
                asyncio.create_task(
                    metrics_collector.increment_counter(
                        "api_errors_total", labels=labels
                    )
                )
                raise
            finally:
                # Записываем время выполнения
                execution_time = time.time() - start_time
                asyncio.create_task(
                    metrics_collector.observe_histogram(
                        "api_call_duration_seconds", execution_time, labels=labels
                    )
                )

        # Определяем, является ли функция асинхронной
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class MetricsContext:
    """Контекстный менеджер для отслеживания метрик"""

    def __init__(
        self,
        metric_name: str,
        metric_type: MetricType = MetricType.COUNTER,
        labels: dict[str, str] | None = None,
    ):
        self.metric_name = metric_name
        self.metric_type = metric_type
        self.labels = labels or {}
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        await metrics_collector.increment_counter(
            f"{self.metric_name}_started_total", labels=self.labels
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time

        if exc_type is None:
            await metrics_collector.increment_counter(
                f"{self.metric_name}_completed_total", labels=self.labels
            )
        else:
            await metrics_collector.increment_counter(
                f"{self.metric_name}_failed_total", labels=self.labels
            )

        await metrics_collector.observe_histogram(
            f"{self.metric_name}_duration_seconds", execution_time, labels=self.labels
        )

    def __enter__(self):
        self.start_time = time.time()
        asyncio.create_task(
            metrics_collector.increment_counter(
                f"{self.metric_name}_started_total", labels=self.labels
            )
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time

        if exc_type is None:
            asyncio.create_task(
                metrics_collector.increment_counter(
                    f"{self.metric_name}_completed_total", labels=self.labels
                )
            )
        else:
            asyncio.create_task(
                metrics_collector.increment_counter(
                    f"{self.metric_name}_failed_total", labels=self.labels
                )
            )

        asyncio.create_task(
            metrics_collector.observe_histogram(
                f"{self.metric_name}_duration_seconds",
                execution_time,
                labels=self.labels,
            )
        )
