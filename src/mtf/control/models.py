"""
Data models for MTF Control module
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SystemStatus(Enum):
    """Статус системы"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class ComponentStatus(Enum):
    """Статус компонента"""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DISABLED = "disabled"


class ControlAction(Enum):
    """Действие управления"""

    START = "start"
    STOP = "stop"
    RESTART = "restart"
    PAUSE = "pause"
    RESUME = "resume"
    CONFIGURE = "configure"
    STATUS = "status"
    HEALTH_CHECK = "health_check"
    METRICS = "metrics"
    LOGS = "logs"


@dataclass
class ControlRequest:
    """Запрос управления"""

    action: ControlAction
    target_component: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    priority: int = 1
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())


@dataclass
class ControlResult:
    """Результат управления"""

    request_id: str
    action: ControlAction
    success: bool
    message: str

    # Результаты компонентов
    component_results: dict[str, Any] = field(default_factory=dict)

    # Метаданные
    start_time: datetime | None = None
    end_time: datetime | None = None
    processing_time_seconds: float | None = None

    # Ошибки и предупреждения
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Дополнительная информация
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """Проверка успешности операции"""
        return self.success and not self.errors


@dataclass
class ControlMetrics:
    """Метрики управления"""

    # Общие метрики
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Метрики по действиям
    start_actions: int = 0
    stop_actions: int = 0
    restart_actions: int = 0
    configure_actions: int = 0
    status_checks: int = 0
    health_checks: int = 0

    # Метрики по компонентам
    context_operations: int = 0
    triggers_operations: int = 0
    consensus_operations: int = 0
    pipeline_operations: int = 0
    integration_operations: int = 0

    # Временные метрики
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0

    # Ошибки
    total_errors: int = 0
    component_errors: int = 0
    configuration_errors: int = 0
    timeout_errors: int = 0

    # Системные метрики
    system_uptime: float = 0.0
    components_ready: int = 0
    components_running: int = 0
    components_error: int = 0


@dataclass
class ControlConfig:
    """Конфигурация управления"""

    # Общие настройки
    max_workers: int = 4
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    # Настройки компонентов
    context_enabled: bool = True
    triggers_enabled: bool = True
    consensus_enabled: bool = True
    pipeline_enabled: bool = True
    integration_enabled: bool = True

    # Настройки мониторинга
    enable_monitoring: bool = True
    monitoring_interval_seconds: int = 60
    health_check_interval_seconds: int = 30
    metrics_collection_interval_seconds: int = 60

    # Настройки алертов
    enable_alerts: bool = True
    alert_threshold_errors: int = 5
    alert_threshold_response_time: float = 10.0
    alert_threshold_memory_usage: float = 80.0
    alert_threshold_cpu_usage: float = 80.0

    # Настройки логирования
    enable_logging: bool = True
    log_level: str = "INFO"
    log_performance: bool = True
    log_retention_days: int = 30

    # Настройки ресурсов
    max_memory_usage_mb: int = 1024
    max_cpu_usage_percent: float = 80.0
    max_concurrent_requests: int = 100

    # Настройки восстановления
    enable_auto_recovery: bool = True
    auto_recovery_attempts: int = 3
    auto_recovery_delay_seconds: float = 5.0

    # Настройки конфигурации
    config_reload_enabled: bool = True
    config_reload_interval_seconds: int = 300

    @classmethod
    def from_yaml(cls, config_path: str) -> "ControlConfig":
        """Загрузка конфигурации из YAML файла"""
        import yaml

        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data.get("control", {}))

    @classmethod
    def default(cls) -> "ControlConfig":
        """Создание конфигурации по умолчанию"""
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "max_workers": self.max_workers,
            "timeout_seconds": self.timeout_seconds,
            "retry_attempts": self.retry_attempts,
            "retry_delay_seconds": self.retry_delay_seconds,
            "context_enabled": self.context_enabled,
            "triggers_enabled": self.triggers_enabled,
            "consensus_enabled": self.consensus_enabled,
            "pipeline_enabled": self.pipeline_enabled,
            "integration_enabled": self.integration_enabled,
            "enable_monitoring": self.enable_monitoring,
            "monitoring_interval_seconds": self.monitoring_interval_seconds,
            "health_check_interval_seconds": self.health_check_interval_seconds,
            "metrics_collection_interval_seconds": self.metrics_collection_interval_seconds,
            "enable_alerts": self.enable_alerts,
            "alert_threshold_errors": self.alert_threshold_errors,
            "alert_threshold_response_time": self.alert_threshold_response_time,
            "alert_threshold_memory_usage": self.alert_threshold_memory_usage,
            "alert_threshold_cpu_usage": self.alert_threshold_cpu_usage,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level,
            "log_performance": self.log_performance,
            "log_retention_days": self.log_retention_days,
            "max_memory_usage_mb": self.max_memory_usage_mb,
            "max_cpu_usage_percent": self.max_cpu_usage_percent,
            "max_concurrent_requests": self.max_concurrent_requests,
            "enable_auto_recovery": self.enable_auto_recovery,
            "auto_recovery_attempts": self.auto_recovery_attempts,
            "auto_recovery_delay_seconds": self.auto_recovery_delay_seconds,
            "config_reload_enabled": self.config_reload_enabled,
            "config_reload_interval_seconds": self.config_reload_interval_seconds,
        }


@dataclass
class SystemState:
    """Состояние системы"""

    status: SystemStatus
    start_time: datetime | None = None
    uptime_seconds: float = 0.0

    # Состояние компонентов
    components: dict[str, ComponentStatus] = field(default_factory=dict)

    # Ресурсы
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

    # Метрики
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Ошибки
    last_error: str | None = None
    error_count: int = 0

    # Дополнительная информация
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Проверка здоровья системы"""
        return (
            self.status == SystemStatus.RUNNING
            and self.error_count < 5
            and self.memory_usage_mb < 1024
            and self.cpu_usage_percent < 80.0
        )

    @property
    def success_rate(self) -> float:
        """Процент успешных запросов"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
