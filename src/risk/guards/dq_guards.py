"""
DQ Guard - защита от плохого качества данных

Основные функции:
- Мониторинг качества данных
- Проверка свежести данных
- Обнаружение аномалий
- Блокировка операций при плохом качестве данных
"""

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import numpy as np

from .models import (
    DQGuardConfig,
    GuardAlert,
    GuardMetrics,
    GuardState,
    GuardStatus,
    GuardType,
)

logger = logging.getLogger(__name__)


class DQGuard:
    """
    DQ Guard для защиты от плохого качества данных

    Основные функции:
    - Мониторинг качества данных
    - Проверка свежести данных
    - Обнаружение аномалий
    - Блокировка операций при плохом качестве данных
    """

    def __init__(self, config: DQGuardConfig | None = None):
        self.config = config or DQGuardConfig(
            guard_type=GuardType.DQ_GUARD, name="default_dq_guard"
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Состояние guard
        self.guard_state = GuardState(guard_id=uuid4(), status=GuardStatus.ACTIVE)

        # Метрики
        self.metrics_history: list[GuardMetrics] = []

        # Алерты
        self.alerts: list[GuardAlert] = []

        # История данных для анализа аномалий
        self.data_history: list[dict[str, Any]] = []

        # Callbacks
        self.on_trigger_callback: Callable | None = None
        self.on_recovery_callback: Callable | None = None

    def check_data_quality(
        self, data: dict[str, Any], data_timestamp: datetime | None = None
    ) -> tuple[bool, list[str]]:
        """
        Проверка качества данных

        Args:
            data: Данные для проверки
            data_timestamp: Временная метка данных

        Returns:
            (качество_хорошее, список_ошибок)
        """
        errors = []

        # Проверка свежести данных
        if data_timestamp:
            freshness_ok, freshness_errors = self._check_data_freshness(data_timestamp)
            if not freshness_ok:
                errors.extend(freshness_errors)

        # Проверка полноты данных
        completeness_ok, completeness_errors = self._check_data_completeness(data)
        if not completeness_ok:
            errors.extend(completeness_errors)

        # Проверка аномалий
        anomaly_ok, anomaly_errors = self._check_data_anomalies(data)
        if not anomaly_ok:
            errors.extend(anomaly_errors)

        # Проверка консистентности
        consistency_ok, consistency_errors = self._check_data_consistency(data)
        if not consistency_ok:
            errors.extend(consistency_errors)

        # Обновляем метрики
        self._update_metrics(data, len(errors) == 0)

        # Проверяем необходимость срабатывания
        if errors and self.guard_state.should_trigger(self.config):
            self._trigger_guard(errors)

        return len(errors) == 0, errors

    def _check_data_freshness(self, data_timestamp: datetime) -> tuple[bool, list[str]]:
        """Проверка свежести данных"""
        errors = []

        now = datetime.utcnow()
        age_sec = (now - data_timestamp).total_seconds()

        if age_sec > self.config.data_freshness_threshold_sec:
            errors.append(
                f"Data too old: {age_sec}s > {self.config.data_freshness_threshold_sec}s"
            )

        return len(errors) == 0, errors

    def _check_data_completeness(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Проверка полноты данных"""
        errors = []

        if not data:
            errors.append("No data provided")
            return False, errors

        # Подсчитываем отсутствующие значения
        total_fields = len(data)
        missing_fields = sum(
            1 for value in data.values() if value is None or value == ""
        )
        missing_percentage = missing_fields / total_fields if total_fields > 0 else 1.0

        if missing_percentage > self.config.missing_data_threshold:
            errors.append(
                f"Too many missing values: {missing_percentage:.2%} > {self.config.missing_data_threshold:.2%}"
            )

        return len(errors) == 0, errors

    def _check_data_anomalies(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Проверка аномалий в данных"""
        errors = []

        # Добавляем данные в историю
        self.data_history.append({"timestamp": datetime.utcnow(), "data": data.copy()})

        # Ограничиваем размер истории
        max_history = 100
        if len(self.data_history) > max_history:
            self.data_history = self.data_history[-max_history:]

        # Проверяем аномалии только если есть достаточно истории
        if len(self.data_history) < 10:
            return True, errors

        # Анализируем числовые поля
        numeric_fields = {}
        for field, value in data.items():
            if isinstance(value, int | float | Decimal):
                numeric_fields[field] = float(value)

        for field, value in numeric_fields.items():
            # Получаем исторические значения
            historical_values = []
            for record in self.data_history[:-1]:  # Исключаем текущую запись
                if field in record["data"] and record["data"][field] is not None:
                    try:
                        historical_values.append(float(record["data"][field]))
                    except (ValueError, TypeError):
                        continue

            if len(historical_values) < 5:
                continue

            # Проверяем на аномалии
            mean = np.mean(historical_values)
            std = np.std(historical_values)

            if std > 0:
                z_score = abs(value - mean) / std
                if z_score > self.config.anomaly_threshold:
                    errors.append(
                        f"Anomaly detected in {field}: z-score {z_score:.2f} > {self.config.anomaly_threshold}"
                    )

        return len(errors) == 0, errors

    def _check_data_consistency(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Проверка консистентности данных"""
        errors = []

        # Проверяем базовую консистентность
        if "price" in data and "volume" in data:
            price = data.get("price")
            volume = data.get("volume")

            if price is not None and volume is not None:
                try:
                    price = float(price)
                    volume = float(volume)

                    # Цена должна быть положительной
                    if price <= 0:
                        errors.append("Price must be positive")

                    # Объем должен быть неотрицательным
                    if volume < 0:
                        errors.append("Volume must be non-negative")

                    # Проверяем разумность значений
                    if price > 1000000:  # 1M - разумный лимит для цены
                        errors.append("Price seems unreasonably high")

                    if volume > 1000000000:  # 1B - разумный лимит для объема
                        errors.append("Volume seems unreasonably high")

                except (ValueError, TypeError):
                    errors.append("Invalid numeric values in price/volume")

        return len(errors) == 0, errors

    def _update_metrics(self, data: dict[str, Any], is_quality_good: bool):
        """Обновление метрик"""
        # Рассчитываем метрику качества
        quality_score = 1.0 if is_quality_good else 0.0

        # Создаем метрику
        metric = GuardMetrics(
            guard_id=self.guard_state.guard_id,
            metric_value=Decimal(str(quality_score)),
            threshold_value=self.config.data_quality_threshold,
            is_triggered=not is_quality_good,
            trigger_count=self.guard_state.trigger_count,
            context={
                "data_fields": list(data.keys()),
                "data_size": len(data),
                "quality_score": quality_score,
            },
        )

        self.metrics_history.append(metric)

        # Ограничиваем размер истории метрик
        max_metrics = 1000
        if len(self.metrics_history) > max_metrics:
            self.metrics_history = self.metrics_history[-max_metrics:]

    def _trigger_guard(self, errors: list[str]):
        """Срабатывание guard"""
        self.guard_state.status = GuardStatus.TRIGGERED
        self.guard_state.trigger_count += 1
        self.guard_state.last_triggered = datetime.utcnow()
        self.guard_state.updated_at = datetime.utcnow()

        # Создаем алерт
        alert = GuardAlert(
            guard_id=self.guard_state.guard_id,
            alert_type="dq_guard_triggered",
            severity="high",
            message=f"Data quality issues detected: {len(errors)} errors",
            context={
                "errors": errors,
                "trigger_count": self.guard_state.trigger_count,
                "data_quality_threshold": float(self.config.data_quality_threshold),
            },
        )
        self.alerts.append(alert)

        # Вызываем callback
        if self.on_trigger_callback:
            self.on_trigger_callback(self, errors)

        self.logger.warning(f"DQ Guard triggered: {len(errors)} data quality issues")

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
            alert_type="dq_guard_recovered",
            severity="medium",
            message="Data quality guard recovered",
            context={
                "recovery_time": datetime.utcnow(),
                "total_triggers": self.guard_state.trigger_count,
            },
        )
        self.alerts.append(alert)

        # Вызываем callback
        if self.on_recovery_callback:
            self.on_recovery_callback(self)

        self.logger.info("DQ Guard recovered")

    def get_status(self) -> dict[str, Any]:
        """Получение статуса DQ guard"""
        return {
            "status": self.guard_state.status.value,
            "is_triggered": self.guard_state.is_triggered(),
            "trigger_count": self.guard_state.trigger_count,
            "last_triggered": self.guard_state.last_triggered,
            "last_recovery": self.guard_state.last_recovery,
            "data_history_size": len(self.data_history),
            "metrics_history_size": len(self.metrics_history),
            "config": {
                "data_freshness_threshold_sec": self.config.data_freshness_threshold_sec,
                "data_quality_threshold": float(self.config.data_quality_threshold),
                "missing_data_threshold": float(self.config.missing_data_threshold),
                "anomaly_threshold": float(self.config.anomaly_threshold),
            },
        }

    def get_metrics(self) -> dict[str, Any]:
        """Получение метрик DQ guard"""
        if not self.metrics_history:
            return {}

        recent_metrics = self.metrics_history[-10:]  # Последние 10 записей

        # Рассчитываем статистику
        quality_scores = [float(m.metric_value) for m in recent_metrics]
        avg_quality = np.mean(quality_scores) if quality_scores else 0.0

        return {
            "avg_quality_score": avg_quality,
            "total_checks": len(self.metrics_history),
            "failed_checks": sum(1 for m in self.metrics_history if not m.is_triggered),
            "success_rate": (
                sum(1 for m in self.metrics_history if m.is_triggered)
                / len(self.metrics_history)
                if self.metrics_history
                else 0.0
            ),
            "recent_metrics": [
                {
                    "timestamp": m.timestamp,
                    "quality_score": float(m.metric_value),
                    "is_triggered": m.is_triggered,
                }
                for m in recent_metrics
            ],
        }

    def get_data_quality_report(self) -> dict[str, Any]:
        """Получение отчета о качестве данных"""
        if not self.data_history:
            return {"message": "No data history available"}

        recent_data = self.data_history[-10:]  # Последние 10 записей

        # Анализируем поля
        field_analysis = {}
        for record in recent_data:
            for field, value in record["data"].items():
                if field not in field_analysis:
                    field_analysis[field] = {
                        "count": 0,
                        "null_count": 0,
                        "numeric_count": 0,
                        "values": [],
                    }

                field_analysis[field]["count"] += 1

                if value is None or value == "":
                    field_analysis[field]["null_count"] += 1
                elif isinstance(value, int | float | Decimal):
                    field_analysis[field]["numeric_count"] += 1
                    field_analysis[field]["values"].append(float(value))

        # Рассчитываем статистику для числовых полей
        for analysis in field_analysis.values():
            if analysis["numeric_count"] > 0:
                values = analysis["values"]
                analysis["mean"] = np.mean(values)
                analysis["std"] = np.std(values)
                analysis["min"] = np.min(values)
                analysis["max"] = np.max(values)
                analysis["null_percentage"] = analysis["null_count"] / analysis["count"]

        return {
            "total_records": len(self.data_history),
            "recent_records": len(recent_data),
            "field_analysis": field_analysis,
            "overall_quality": self.get_metrics().get("avg_quality_score", 0.0),
        }

    def update_config(self, **kwargs):
        """Обновление конфигурации"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        self.config.updated_at = datetime.utcnow()
        self.logger.info(f"Updated DQ guard config: {kwargs}")

    def reset(self):
        """Сброс DQ guard"""
        self.guard_state.status = GuardStatus.ACTIVE
        self.guard_state.trigger_count = 0
        self.guard_state.last_triggered = None
        self.guard_state.last_recovery = None
        self.guard_state.updated_at = datetime.utcnow()

        # Очищаем историю
        self.data_history.clear()
        self.metrics_history.clear()

        self.logger.info("DQ Guard reset")

    def set_callbacks(
        self,
        on_trigger: Callable | None = None,
        on_recovery: Callable | None = None,
    ):
        """Установка callbacks"""
        self.on_trigger_callback = on_trigger
        self.on_recovery_callback = on_recovery

        self.logger.info("DQ Guard callbacks set")

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


class DQGuardManager:
    """
    Менеджер DQ guards

    Управляет множественными DQ guards для разных типов данных
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.dq_guards: dict[str, DQGuard] = {}

    def create_dq_guard(
        self, name: str, config: DQGuardConfig | None = None
    ) -> DQGuard:
        """Создание DQ guard"""
        if name in self.dq_guards:
            raise ValueError(f"DQ Guard '{name}' already exists")

        if config is None:
            config = DQGuardConfig(guard_type=GuardType.DQ_GUARD, name=name)

        dq_guard = DQGuard(config)
        self.dq_guards[name] = dq_guard

        self.logger.info(f"Created DQ Guard: {name}")
        return dq_guard

    def get_dq_guard(self, name: str) -> DQGuard | None:
        """Получение DQ guard"""
        return self.dq_guards.get(name)

    def check_data_quality(
        self, name: str, data: dict[str, Any], data_timestamp: datetime | None = None
    ) -> tuple[bool, list[str]]:
        """Проверка качества данных через DQ guard"""
        dq_guard = self.get_dq_guard(name)
        if dq_guard is None:
            raise ValueError(f"DQ Guard '{name}' not found")

        return dq_guard.check_data_quality(data, data_timestamp)

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Получение статуса всех DQ guards"""
        return {
            name: dq_guard.get_status() for name, dq_guard in self.dq_guards.items()
        }

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Получение метрик всех DQ guards"""
        return {
            name: dq_guard.get_metrics() for name, dq_guard in self.dq_guards.items()
        }

    def get_overall_data_quality(self) -> dict[str, Any]:
        """Получение общего качества данных"""
        if not self.dq_guards:
            return {"message": "No DQ guards available"}

        total_quality = 0.0
        total_guards = len(self.dq_guards)

        for dq_guard in self.dq_guards.values():
            metrics = dq_guard.get_metrics()
            quality = metrics.get("avg_quality_score", 0.0)
            total_quality += quality

        avg_quality = total_quality / total_guards if total_guards > 0 else 0.0

        return {
            "overall_quality_score": avg_quality,
            "total_guards": total_guards,
            "quality_by_guard": {
                name: dq_guard.get_metrics().get("avg_quality_score", 0.0)
                for name, dq_guard in self.dq_guards.items()
            },
        }

    def reset_all(self):
        """Сброс всех DQ guards"""
        for dq_guard in self.dq_guards.values():
            dq_guard.reset()

        self.logger.info("All DQ guards reset")

    def check_all_recovery(self):
        """Проверка восстановления всех DQ guards"""
        for dq_guard in self.dq_guards.values():
            dq_guard.check_recovery()
