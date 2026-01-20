#!/usr/bin/env python3
"""
MTF Run Tracker

Система трассировки выполнения MTF операций с:
- Уникальными run_id для каждого запуска
- Версионированием алгоритмов и параметров
- Метриками производительности
- Логированием с контекстом
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

from src.mtf.config.settings import mtf_config
from src.mtf.monitoring.alerts import alert_manager


@dataclass
class RunContext:
    """Контекст выполнения"""

    run_id: str
    start_time: datetime
    end_time: datetime | None = None
    status: str = "running"
    source: str = "mtf"
    version: str = "1.0.0"
    params_hash: str = ""
    git_sha: str = ""
    env_hash: str = ""

    # Метрики
    rows_processed: int = 0
    rows_written: int = 0
    errors_count: int = 0
    warnings_count: int = 0

    # Дополнительная информация
    metadata: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float | None:
        """Длительность выполнения в секундах"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def is_completed(self) -> bool:
        """Завершено ли выполнение"""
        return self.status in ["completed", "failed", "cancelled"]


class RunTracker:
    """Трекер выполнения операций"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_runs: dict[str, RunContext] = {}
        self.completed_runs: list[RunContext] = []
        self.max_completed_runs = 1000

        # Генерация хешей окружения
        self.env_hash = self._generate_env_hash()
        self.params_hash = self._generate_params_hash()

    def _generate_env_hash(self) -> str:
        """Генерировать хеш окружения"""
        env_data = {
            "python_version": f"{mtf_config.version}",
            "schema_version": mtf_config.schema_version,
            "config_hash": self._hash_config(),
        }
        return hashlib.md5(json.dumps(env_data, sort_keys=True).encode()).hexdigest()[
            :8
        ]

    def _generate_params_hash(self) -> str:
        """Генерировать хеш параметров"""
        params_data = {
            "timeframes": list(mtf_config.timeframes.keys()),
            "consensus_mode": mtf_config.consensus.mode.value,
            "risk_config": {
                "max_position_size": mtf_config.risk.max_position_size,
                "daily_loss_limit": mtf_config.risk.daily_loss_limit,
            },
        }
        return hashlib.md5(
            json.dumps(params_data, sort_keys=True).encode()
        ).hexdigest()[:8]

    def _hash_config(self) -> str:
        """Хешировать конфигурацию"""
        config_str = json.dumps(mtf_config.__dict__, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]

    def start_run(
        self, source: str = "mtf", metadata: dict[str, Any] | None = None
    ) -> str:
        """Начать новое выполнение"""
        run_id = str(uuid.uuid4())

        context = RunContext(
            run_id=run_id,
            start_time=datetime.utcnow(),
            source=source,
            version=mtf_config.version,
            params_hash=self.params_hash,
            env_hash=self.env_hash,
            metadata=metadata or {},
        )

        self.active_runs[run_id] = context

        self.logger.info(f"🚀 Запуск {source} с run_id: {run_id}")
        self.logger.info(
            f"📊 Версия: {context.version}, Параметры: {context.params_hash}"
        )

        return run_id

    def end_run(
        self, run_id: str, status: str = "completed", error: str | None = None
    ) -> bool:
        """Завершить выполнение"""
        if run_id not in self.active_runs:
            self.logger.warning(f"Попытка завершить несуществующий run_id: {run_id}")
            return False

        context = self.active_runs[run_id]
        context.end_time = datetime.utcnow()
        context.status = status

        if error:
            context.metadata["error"] = error
            context.errors_count += 1

        # Перемещаем в завершенные
        self.completed_runs.append(context)
        del self.active_runs[run_id]

        # Ограничиваем количество сохраненных запусков
        if len(self.completed_runs) > self.max_completed_runs:
            self.completed_runs.pop(0)

        duration = context.duration
        self.logger.info(
            f"✅ Завершение {context.source} (run_id: {run_id}) "
            f"статус: {status}, длительность: {duration:.2f}с"
        )

        # Отправляем алерт при ошибке
        if status == "failed" and error:
            asyncio.create_task(
                alert_manager.send_error_alert(
                    f"Ошибка выполнения {context.source}",
                    f"Run ID: {run_id}\nОшибка: {error}\nДлительность: {duration:.2f}с",
                    source="RunTracker",
                )
            )

        return True

    def add_step(
        self,
        run_id: str,
        step_name: str,
        duration: float,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Добавить шаг выполнения"""
        if run_id not in self.active_runs:
            return False

        context = self.active_runs[run_id]
        step = {
            "name": step_name,
            "duration": duration,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {},
        }
        context.steps.append(step)

        self.logger.debug(f"📝 Шаг {step_name} для run_id {run_id}: {duration:.3f}с")
        return True

    def update_metrics(
        self,
        run_id: str,
        rows_processed: int = 0,
        rows_written: int = 0,
        errors: int = 0,
        warnings: int = 0,
    ) -> bool:
        """Обновить метрики выполнения"""
        if run_id not in self.active_runs:
            return False

        context = self.active_runs[run_id]
        context.rows_processed += rows_processed
        context.rows_written += rows_written
        context.errors_count += errors
        context.warnings_count += warnings

        return True

    def get_run_context(self, run_id: str) -> RunContext | None:
        """Получить контекст выполнения"""
        return self.active_runs.get(run_id) or next(
            (run for run in self.completed_runs if run.run_id == run_id), None
        )

    def get_active_runs(self) -> list[RunContext]:
        """Получить активные выполнения"""
        return list(self.active_runs.values())

    def get_recent_runs(
        self, hours: int = 24, source: str | None = None
    ) -> list[RunContext]:
        """Получить недавние выполнения"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        recent_runs = [
            run for run in self.completed_runs if run.start_time >= cutoff_time
        ]

        if source:
            recent_runs = [run for run in recent_runs if run.source == source]

        return recent_runs

    def get_run_stats(self, hours: int = 24) -> dict[str, Any]:
        """Получить статистику выполнения"""
        recent_runs = self.get_recent_runs(hours)

        if not recent_runs:
            return {
                "total_runs": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "total_rows_processed": 0,
                "total_errors": 0,
            }

        completed_runs = [run for run in recent_runs if run.is_completed]
        successful_runs = [run for run in completed_runs if run.status == "completed"]

        durations = [run.duration for run in completed_runs if run.duration is not None]

        return {
            "total_runs": len(recent_runs),
            "completed_runs": len(completed_runs),
            "success_rate": (
                len(successful_runs) / len(completed_runs) if completed_runs else 0.0
            ),
            "avg_duration": sum(durations) / len(durations) if durations else 0.0,
            "total_rows_processed": sum(run.rows_processed for run in recent_runs),
            "total_rows_written": sum(run.rows_written for run in recent_runs),
            "total_errors": sum(run.errors_count for run in recent_runs),
            "total_warnings": sum(run.warnings_count for run in recent_runs),
        }


# Глобальный экземпляр трекера
run_tracker = RunTracker()


def track_run(source: str = "mtf"):
    """Декоратор для автоматического трекинга выполнения"""

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            run_id = run_tracker.start_run(source)

            try:
                start_time = time.time()
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                run_tracker.add_step(run_id, func.__name__, duration)
                run_tracker.end_run(run_id, "completed")

                return result

            except Exception as e:
                duration = time.time() - start_time
                run_tracker.add_step(run_id, func.__name__, duration, {"error": str(e)})
                run_tracker.end_run(run_id, "failed", str(e))
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            run_id = run_tracker.start_run(source)

            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                run_tracker.add_step(run_id, func.__name__, duration)
                run_tracker.end_run(run_id, "completed")

                return result

            except Exception as e:
                duration = time.time() - start_time
                run_tracker.add_step(run_id, func.__name__, duration, {"error": str(e)})
                run_tracker.end_run(run_id, "failed", str(e))
                raise

        # Определяем тип функции
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@asynccontextmanager
async def run_context(source: str = "mtf", metadata: dict[str, Any] | None = None):
    """Контекстный менеджер для трекинга выполнения"""
    run_id = run_tracker.start_run(source, metadata)

    try:
        yield run_id
        run_tracker.end_run(run_id, "completed")
    except Exception as e:
        run_tracker.end_run(run_id, "failed", str(e))
        raise


class RunLogger:
    """Логгер с контекстом выполнения"""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.logger = logging.getLogger(__name__)

    def info(self, message: str, **kwargs):
        """Логировать информационное сообщение"""
        self.logger.info(f"[{self.run_id}] {message}", **kwargs)

    def warning(self, message: str, **kwargs):
        """Логировать предупреждение"""
        self.logger.warning(f"[{self.run_id}] {message}", **kwargs)
        run_tracker.update_metrics(self.run_id, warnings=1)

    def error(self, message: str, **kwargs):
        """Логировать ошибку"""
        self.logger.error(f"[{self.run_id}] {message}", **kwargs)
        run_tracker.update_metrics(self.run_id, errors=1)

    def debug(self, message: str, **kwargs):
        """Логировать отладочное сообщение"""
        self.logger.debug(f"[{self.run_id}] {message}", **kwargs)


def get_run_logger(run_id: str) -> RunLogger:
    """Получить логгер с контекстом выполнения"""
    return RunLogger(run_id)
