"""
SLA Guard - защита от нарушения SLA

Основные функции:
- Мониторинг производительности системы
- Проверка задержек (latency)
- Контроль пропускной способности (throughput)
- Мониторинг доступности (availability)
"""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from .models import (
    GuardAlert,
    GuardMetrics,
    GuardState,
    GuardStatus,
    GuardType,
    SLAGuardConfig,
)

logger = logging.getLogger(__name__)


class SLAGuard:
    """
    SLA Guard для защиты от нарушения SLA

    Основные функции:
    - Мониторинг производительности системы
    - Проверка задержек (latency)
    - Контроль пропускной способности (throughput)
    - Мониторинг доступности (availability)
    """

    def __init__(self, config: SLAGuardConfig | None = None):
        self.config = config or SLAGuardConfig(
            guard_type=GuardType.SLA_GUARD, name="default_sla_guard"
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние guard
        self.guard_state = GuardState(guard_id=uuid4(), status=GuardStatus.ACTIVE)

        # Метрики
        self.metrics_history: list[GuardMetrics] = []

        # Алерты
        self.alerts: list[GuardAlert] = []

        # История операций для расчета SLA
        self.operation_history: list[dict[str, Any]] = []

        # Callbacks
        self.on_trigger_callback: Callable | None = None
        self.on_recovery_callback: Callable | None = None

    def record_operation(
        self,
        operation_name: str,
        start_time: datetime,
        end_time: datetime,
        success: bool,
        error_message: str | None = None,
    ):
        """
        Запись операции для мониторинга SLA

        Args:
            operation_name: Название операции
            start_time: Время начала операции
            end_time: Время окончания операции
            success: Успешность операции
            error_message: Сообщение об ошибке (если есть)
        """
        # Рассчитываем метрики
        duration_ms = (end_time - start_time).total_seconds() * 1000

        # Записываем операцию
        operation_record = {
            "operation_name": operation_name,
            "start_time": start_time,
            "end_time": end_time,
            "duration_ms": duration_ms,
            "success": success,
            "error_message": error_message,
            "timestamp": datetime.utcnow(),
        }

        self.operation_history.append(operation_record)

        # Ограничиваем размер истории
        max_history = 1000
        if len(self.operation_history) > max_history:
            self.operation_history = self.operation_history[-max_history:]

        # Проверяем SLA
        self._check_sla_violations()

    def _check_sla_violations(self):
        """Проверка нарушений SLA"""
        if len(self.operation_history) < 10:  # Минимум операций для анализа
            return

        # Получаем последние операции
        recent_operations = self.operation_history[-100:]  # Последние 100 операций

        # Рассчитываем метрики
        sla_metrics = self._calculate_sla_metrics(recent_operations)

        # Проверяем нарушения
        violations = []

        # Проверка latency
        if sla_metrics["avg_latency_ms"] > self.config.latency_threshold_ms:
            violations.append(
                f"Latency SLA violated: {sla_metrics['avg_latency_ms']:.1f}ms > {self.config.latency_threshold_ms}ms"
            )

        # Проверка throughput
        if sla_metrics["throughput_ops_per_sec"] < self.config.throughput_threshold:
            violations.append(
                f"Throughput SLA violated: {sla_metrics['throughput_ops_per_sec']:.1f} ops/sec < {self.config.throughput_threshold} ops/sec"
            )

        # Проверка error rate
        if sla_metrics["error_rate"] > self.config.error_rate_threshold:
            violations.append(
                f"Error rate SLA violated: {sla_metrics['error_rate']:.2%} > {self.config.error_rate_threshold:.2%}"
            )

        # Проверка availability
        if sla_metrics["availability"] < self.config.availability_threshold:
            violations.append(
                f"Availability SLA violated: {sla_metrics['availability']:.2%} < {self.config.availability_threshold:.2%}"
            )

        # Обновляем метрики
        self._update_metrics(sla_metrics, len(violations) == 0)

        # Проверяем необходимость срабатывания
        if violations and self.guard_state.should_trigger(self.config):
            self._trigger_guard(violations)

    def _calculate_sla_metrics(
        self, operations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Расчет метрик SLA"""
        if not operations:
            return {}

        # Рассчитываем latency
        latencies = [op["duration_ms"] for op in operations]
        avg_latency_ms = sum(latencies) / len(latencies)
        max_latency_ms = max(latencies)
        min_latency_ms = min(latencies)

        # Рассчитываем throughput
        time_span_sec = (
            operations[-1]["end_time"] - operations[0]["start_time"]
        ).total_seconds()
        throughput_ops_per_sec = (
            len(operations) / time_span_sec if time_span_sec > 0 else 0
        )

        # Рассчитываем error rate
        successful_ops = sum(1 for op in operations if op["success"])
        error_rate = (len(operations) - successful_ops) / len(operations)

        # Рассчитываем availability
        availability = successful_ops / len(operations)

        return {
            "avg_latency_ms": avg_latency_ms,
            "max_latency_ms": max_latency_ms,
            "min_latency_ms": min_latency_ms,
            "throughput_ops_per_sec": throughput_ops_per_sec,
            "error_rate": error_rate,
            "availability": availability,
            "total_operations": len(operations),
            "successful_operations": successful_ops,
            "failed_operations": len(operations) - successful_ops,
        }

    def _update_metrics(self, sla_metrics: dict[str, Any], is_sla_good: bool):
        """Обновление метрик"""
        # Рассчитываем общий SLA score
        sla_score = 1.0 if is_sla_good else 0.0

        # Создаем метрику
        metric = GuardMetrics(
            guard_id=self.guard_state.guard_id,
            metric_value=Decimal(str(sla_score)),
            threshold_value=self.config.threshold,
            is_triggered=not is_sla_good,
            trigger_count=self.guard_state.trigger_count,
            context={"sla_metrics": sla_metrics, "sla_score": sla_score},
        )

        self.metrics_history.append(metric)

        # Ограничиваем размер истории метрик
        max_metrics = 1000
        if len(self.metrics_history) > max_metrics:
            self.metrics_history = self.metrics_history[-max_metrics:]

    def _trigger_guard(self, violations: list[str]):
        """Срабатывание guard"""
        self.guard_state.status = GuardStatus.TRIGGERED
        self.guard_state.trigger_count += 1
        self.guard_state.last_triggered = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="sla_guard_triggered",
            severity="high",
            message=f"SLA violations detected: {len(violations)} violations",
            context={
                "violations": violations,
                "trigger_count": self.guard_state.trigger_count,
                "threshold": float(self.config.threshold),
            },
        )
        self.alerts.append(alert)

        # Вызываем callback
        if self.on_trigger_callback:
            self.on_trigger_callback(self, violations)

        self.logger.warning(f"SLA Guard triggered: {len(violations)} SLA violations")

    def check_recovery(self):
        """Проверка восстановления"""
        if self.guard_state.can_recover(self.config):
            self._recover_guard()

    def _recover_guard(self):
        """Восстановление guard"""
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.last_recovery = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="sla_guard_recovered",
            severity="medium",
            message="SLA guard recovered",
            context={
                "recovery_time": datetime.utcnow(),
                "total_triggers": self.guard_state.trigger_count,
            },
        )
        self.alerts.append(alert)

        # Вызываем callback
        if self.on_recovery_callback:
            self.on_recovery_callback(self)

        self.logger.info("SLA Guard recovered")

    def get_status(self) -> dict[str, Any]:
        """Получение статуса SLA guard"""
        return {
            "status": self.guard_state.status.value,
            "is_triggered": self.guard_state.is_triggered(),
            "trigger_count": self.guard_state.trigger_count,
            "last_triggered": self.guard_state.last_triggered,
            "last_recovery": self.guard_state.last_recovery,
            "operation_history_size": len(self.operation_history),
            "metrics_history_size": len(self.metrics_history),
            "config": {
                "latency_threshold_ms": self.config.latency_threshold_ms,
                "throughput_threshold": self.config.throughput_threshold,
                "error_rate_threshold": float(self.config.error_rate_threshold),
                "availability_threshold": float(self.config.availability_threshold),
            },
        }

    def get_metrics(self) -> dict[str, Any]:
        """Получение метрик SLA guard"""
        if not self.metrics_history:
            return {}

        recent_metrics = self.metrics_history[-10:]  # Последние 10 записей

        # Рассчитываем статистику
        sla_scores = [float(m.metric_value) for m in recent_metrics]
        avg_sla_score = sum(sla_scores) / len(sla_scores) if sla_scores else 0.0

        return {
            "avg_sla_score": avg_sla_score,
            "total_operations": len(self.operation_history),
            "failed_operations": sum(
                1 for m in self.metrics_history if not m.is_triggered
            ),
            "success_rate": (
                sum(1 for m in self.metrics_history if m.is_triggered)
                / len(self.metrics_history)
                if self.metrics_history
                else 0.0
            ),
            "recent_metrics": [
                {
                    "timestamp": m.timestamp,
                    "sla_score": float(m.metric_value),
                    "is_triggered": m.is_triggered,
                }
                for m in recent_metrics
            ],
        }

    def get_sla_report(self) -> dict[str, Any]:
        """Получение отчета по SLA"""
        if not self.operation_history:
            return {"message": "No operation history available"}

        recent_operations = self.operation_history[-100:]  # Последние 100 операций

        # Рассчитываем метрики
        sla_metrics = self._calculate_sla_metrics(recent_operations)

        # Анализируем по типам операций
        operation_types = {}
        for op in recent_operations:
            op_name = op["operation_name"]
            if op_name not in operation_types:
                operation_types[op_name] = []
            operation_types[op_name].append(op)

        operation_analysis = {}
        for op_name, ops in operation_types.items():
            if ops:
                op_metrics = self._calculate_sla_metrics(ops)
                operation_analysis[op_name] = op_metrics

        return {
            "overall_metrics": sla_metrics,
            "operation_analysis": operation_analysis,
            "total_operations": len(self.operation_history),
            "recent_operations": len(recent_operations),
            "sla_compliance": {
                "latency_ok": sla_metrics.get("avg_latency_ms", 0)
                <= self.config.latency_threshold_ms,
                "throughput_ok": sla_metrics.get("throughput_ops_per_sec", 0)
                >= self.config.throughput_threshold,
                "error_rate_ok": sla_metrics.get("error_rate", 0)
                <= self.config.error_rate_threshold,
                "availability_ok": sla_metrics.get("availability", 0)
                >= self.config.availability_threshold,
            },
        }

    def update_config(self, **kwargs):
        """Обновление конфигурации"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        self.config.updated_at = datetime.utcnow()
        self.logger.info(f"Updated SLA guard config: {kwargs}")

    def reset(self):
        """Сброс SLA guard"""
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.trigger_count = 0
        self.guard_state.last_triggered = None
        self.guard_state.last_recovery = None
        self.guard_state.updated_at = datetime.utcnow()

        # Очищаем историю
        self.operation_history.clear()
        self.metrics_history.clear()

        self.logger.info("SLA Guard reset")

    def set_callbacks(
        self,
        on_trigger: Callable | None = None,
        on_recovery: Callable | None = None,
    ):
        """Установка callbacks"""
        self.on_trigger_callback = on_trigger
        self.on_recovery_callback = on_recovery

        self.logger.info("SLA Guard callbacks set")

    def get_alerts(self, unacknowledged_only: bool = True) -> list[GuardAlert]:
        """Получение алертов"""
        if unacknowledged_only:
            return [alert for alert in self.alerts if not alert.acknowledged]
        return self.alerts

    def acknowledge_alert(self, alert_id: UUID, acknowledged_by: str):
        """Подтверждение алерта"""
        for alert in self.alerts:
            if alert.guard_id == alert_id:
                alert.acknowledge(acknowledged_by)
                self.logger.info(f"Alert acknowledged by {acknowledged_by}")
                break


class SLAGuardManager:
    """
    Менеджер SLA guards

    Управляет множественными SLA guards для разных компонентов системы
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.sla_guards: dict[str, SLAGuard] = {}

    def create_sla_guard(
        self, name: str, config: SLAGuardConfig | None = None
    ) -> SLAGuard:
        """Создание SLA guard"""
        if name in self.sla_guards:
            raise ValueError(f"SLA Guard '{name}' already exists")

        if config is None:
            config = SLAGuardConfig(guard_type=GuardType.SLA_GUARD, name=name)

        sla_guard = SLAGuard(config)
        self.sla_guards[name] = sla_guard

        self.logger.info(f"Created SLA Guard: {name}")
        return sla_guard

    def get_sla_guard(self, name: str) -> SLAGuard | None:
        """Получение SLA guard"""
        return self.sla_guards.get(name)

    def record_operation(
        self,
        name: str,
        operation_name: str,
        start_time: datetime,
        end_time: datetime,
        success: bool,
        error_message: str | None = None,
    ):
        """Запись операции через SLA guard"""
        sla_guard = self.get_sla_guard(name)
        if sla_guard is None:
            raise ValueError(f"SLA Guard '{name}' not found")

        sla_guard.record_operation(
            operation_name, start_time, end_time, success, error_message
        )

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Получение статуса всех SLA guards"""
        return {
            name: sla_guard.get_status() for name, sla_guard in self.sla_guards.items()
        }

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Получение метрик всех SLA guards"""
        return {
            name: sla_guard.get_metrics() for name, sla_guard in self.sla_guards.items()
        }

    def get_overall_sla(self) -> dict[str, Any]:
        """Получение общего SLA"""
        if not self.sla_guards:
            return {"message": "No SLA guards available"}

        total_sla = 0.0
        total_guards = len(self.sla_guards)

        for sla_guard in self.sla_guards.values():
            metrics = sla_guard.get_metrics()
            sla_score = metrics.get("avg_sla_score", 0.0)
            total_sla += sla_score

        avg_sla = total_sla / total_guards if total_guards > 0 else 0.0

        return {
            "overall_sla_score": avg_sla,
            "total_guards": total_guards,
            "sla_by_guard": {
                name: sla_guard.get_metrics().get("avg_sla_score", 0.0)
                for name, sla_guard in self.sla_guards.items()
            },
        }

    def reset_all(self):
        """Сброс всех SLA guards"""
        for sla_guard in self.sla_guards.values():
            sla_guard.reset()

        self.logger.info("All SLA guards reset")

    def check_all_recovery(self):
        """Проверка восстановления всех SLA guards"""
        for sla_guard in self.sla_guards.values():
            sla_guard.check_recovery()
