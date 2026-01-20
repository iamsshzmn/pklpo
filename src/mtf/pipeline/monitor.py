"""
Мониторинг для Pipeline Orchestrator
"""

from datetime import datetime, timedelta
from typing import Any

import psutil

from .models import ExecutionMetrics, PipelineHealth, PipelineStatus


class PipelineMonitor:
    """Мониторинг выполнения пайплайна"""

    def __init__(self, enable_metrics: bool = True):
        self.enable_metrics = enable_metrics
        self.active_runs: dict[str, dict[str, Any]] = {}
        self.run_history: list[dict[str, Any]] = []
        self.system_metrics: list[dict[str, Any]] = []

    def start_monitoring(self, run_id: str, symbol: str) -> None:
        """Начало мониторинга запуска"""
        if not self.enable_metrics:
            return

        self.active_runs[run_id] = {
            "symbol": symbol,
            "start_time": datetime.now(),
            "stage": "initializing",
            "memory_start": self._get_memory_usage(),
            "cpu_start": self._get_cpu_usage(),
        }

    def update_stage(self, run_id: str, stage: str) -> None:
        """Обновление текущего этапа"""
        if not self.enable_metrics or run_id not in self.active_runs:
            return

        self.active_runs[run_id]["stage"] = stage
        self.active_runs[run_id]["stage_start_time"] = datetime.now()

    def stop_monitoring(
        self,
        run_id: str,
        status: PipelineStatus,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> ExecutionMetrics:
        """Остановка мониторинга и получение метрик"""
        if not self.enable_metrics or run_id not in self.active_runs:
            return ExecutionMetrics(
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0,
                symbols_processed=0,
                symbols_successful=0,
                symbols_failed=0,
                errors_count=0,
                warnings_count=0,
            )

        run_data = self.active_runs[run_id]
        end_time = datetime.now()
        duration = (end_time - run_data["start_time"]).total_seconds()

        # Расчет использования ресурсов
        memory_usage = self._get_memory_usage() - run_data.get("memory_start", 0)
        cpu_usage = self._get_cpu_usage()

        # Создание метрик
        metrics = ExecutionMetrics(
            start_time=run_data["start_time"],
            end_time=end_time,
            duration_seconds=duration,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            symbols_processed=1,
            symbols_successful=1 if status == PipelineStatus.COMPLETED else 0,
            symbols_failed=1 if status == PipelineStatus.FAILED else 0,
            errors_count=len(errors) if errors else 0,
            warnings_count=len(warnings) if warnings else 0,
        )

        # Сохранение в историю
        self.run_history.append(
            {
                "run_id": run_id,
                "symbol": run_data["symbol"],
                "status": status.value,
                "start_time": run_data["start_time"],
                "end_time": end_time,
                "duration_seconds": duration,
                "memory_usage_mb": memory_usage,
                "cpu_usage_percent": cpu_usage,
                "errors_count": metrics.errors_count,
                "warnings_count": metrics.warnings_count,
            }
        )

        # Удаление из активных запусков
        del self.active_runs[run_id]

        return metrics

    def get_pipeline_health(self) -> PipelineHealth:
        """Получение состояния здоровья пайплайна"""
        if not self.enable_metrics:
            return PipelineHealth(
                status="disabled",
                last_run_time=None,
                success_rate=0.0,
                average_duration=0.0,
                error_rate=0.0,
                active_runs=0,
                queue_size=0,
                system_resources={},
                alerts=[],
            )

        # Анализ последних запусков
        recent_runs = [
            run
            for run in self.run_history
            if run["start_time"] > datetime.now() - timedelta(hours=24)
        ]

        if not recent_runs:
            return PipelineHealth(
                status="no_data",
                last_run_time=None,
                success_rate=0.0,
                average_duration=0.0,
                error_rate=0.0,
                active_runs=len(self.active_runs),
                queue_size=0,
                system_resources=self._get_system_resources(),
                alerts=["No recent runs found"],
            )

        # Расчет метрик
        successful_runs = [run for run in recent_runs if run["status"] == "completed"]
        failed_runs = [run for run in recent_runs if run["status"] == "failed"]

        success_rate = len(successful_runs) / len(recent_runs) if recent_runs else 0.0
        error_rate = len(failed_runs) / len(recent_runs) if recent_runs else 0.0
        average_duration = sum(run["duration_seconds"] for run in recent_runs) / len(
            recent_runs
        )

        # Определение статуса
        if success_rate >= 0.95:
            status = "healthy"
        elif success_rate >= 0.8:
            status = "warning"
        else:
            status = "critical"

        # Проверка алертов
        alerts = []
        if error_rate > 0.1:
            alerts.append(f"High error rate: {error_rate:.1%}")
        if average_duration > 300:  # 5 минут
            alerts.append(f"Slow execution: {average_duration:.1f}s average")
        if len(self.active_runs) > 10:
            alerts.append(f"Too many active runs: {len(self.active_runs)}")

        return PipelineHealth(
            status=status,
            last_run_time=(
                max(run["start_time"] for run in recent_runs) if recent_runs else None
            ),
            success_rate=success_rate,
            average_duration=average_duration,
            error_rate=error_rate,
            active_runs=len(self.active_runs),
            queue_size=0,  # TODO: Implement queue monitoring
            system_resources=self._get_system_resources(),
            alerts=alerts,
        )

    def get_execution_metrics(self, hours: int = 24) -> dict[str, Any]:
        """Получение метрик выполнения за период"""
        if not self.enable_metrics:
            return {}

        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_runs = [
            run for run in self.run_history if run["start_time"] > cutoff_time
        ]

        if not recent_runs:
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "total_duration": 0.0,
                "memory_usage_avg": 0.0,
                "cpu_usage_avg": 0.0,
            }

        successful_runs = [run for run in recent_runs if run["status"] == "completed"]
        failed_runs = [run for run in recent_runs if run["status"] == "failed"]

        return {
            "total_runs": len(recent_runs),
            "successful_runs": len(successful_runs),
            "failed_runs": len(failed_runs),
            "success_rate": len(successful_runs) / len(recent_runs),
            "average_duration": sum(run["duration_seconds"] for run in recent_runs)
            / len(recent_runs),
            "total_duration": sum(run["duration_seconds"] for run in recent_runs),
            "memory_usage_avg": sum(run["memory_usage_mb"] for run in recent_runs)
            / len(recent_runs),
            "cpu_usage_avg": sum(run["cpu_usage_percent"] for run in recent_runs)
            / len(recent_runs),
        }

    def _get_memory_usage(self) -> float:
        """Получение использования памяти в MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except:
            return 0.0

    def _get_cpu_usage(self) -> float:
        """Получение использования CPU в процентах"""
        try:
            return psutil.cpu_percent(interval=0.1)
        except:
            return 0.0

    def _get_system_resources(self) -> dict[str, float]:
        """Получение системных ресурсов"""
        try:
            return {
                "memory_percent": psutil.virtual_memory().percent,
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "disk_percent": psutil.disk_usage("/").percent,
            }
        except:
            return {"memory_percent": 0.0, "cpu_percent": 0.0, "disk_percent": 0.0}
