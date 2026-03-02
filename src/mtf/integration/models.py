"""
Data models for MTF Integration module
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd

from ..pipeline.models import PipelineResult


class DataSource(Enum):
    """Источники данных"""

    OKX_API = "okx_api"
    DATABASE = "database"
    CACHE = "cache"
    FILE = "file"


class NotificationType(Enum):
    """Типы уведомлений"""

    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"


class IntegrationStatus(Enum):
    """Статус интеграции"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IntegrationRequest:
    """Запрос на интеграцию"""

    symbol: str
    timeframes: list[str]
    data_sources: list[DataSource]
    notification_types: list[NotificationType] = field(default_factory=list)
    request_id: str | None = None
    priority: int = 1
    timeout_seconds: float | None = None
    pipeline_result: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Настройки для конкретных источников
    okx_config: dict[str, Any] | None = None
    database_config: dict[str, Any] | None = None
    notification_config: dict[str, Any] | None = None


@dataclass
class IntegrationResult:
    """Результат интеграции"""

    request_id: str
    symbol: str
    timeframes: list[str]
    status: IntegrationStatus

    # Результаты из разных источников
    market_data: pd.DataFrame | None = None
    pipeline_result: PipelineResult | None = None
    database_result: dict[str, Any] | None = None
    notification_result: dict[str, Any] | None = None

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
        """Проверка успешности интеграции"""
        return self.status == IntegrationStatus.COMPLETED and not self.errors

    @property
    def has_market_data(self) -> bool:
        """Проверка наличия рыночных данных"""
        return self.market_data is not None and not self.market_data.empty

    @property
    def has_pipeline_result(self) -> bool:
        """Проверка наличия результата pipeline"""
        return self.pipeline_result is not None and self.pipeline_result.is_successful


@dataclass
class IntegrationMetrics:
    """Метрики интеграции"""

    # Общие метрики
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0

    # Временные метрики
    avg_processing_time: float = 0.0
    min_processing_time: float = 0.0
    max_processing_time: float = 0.0

    # Метрики по источникам данных
    okx_api_calls: int = 0
    database_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    # Метрики по уведомлениям
    notifications_sent: int = 0
    slack_notifications: int = 0
    email_notifications: int = 0
    webhook_notifications: int = 0

    # Метрики по символам
    symbols_processed: int = 0
    unique_symbols: int = 0

    # Метрики по таймфреймам
    timeframes_processed: int = 0
    avg_timeframes_per_request: float = 0.0

    # Ошибки
    total_errors: int = 0
    okx_errors: int = 0
    database_errors: int = 0
    notification_errors: int = 0

    # Производительность
    data_fetch_time: float = 0.0
    pipeline_processing_time: float = 0.0
    database_save_time: float = 0.0
    notification_time: float = 0.0


@dataclass
class IntegrationConfig:
    """Конфигурация интеграции"""

    # Общие настройки
    max_workers: int = 4
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    # Настройки OKX API
    okx_enabled: bool = True
    okx_api_key: str | None = None
    okx_secret_key: str | None = None
    okx_passphrase: str | None = None
    okx_sandbox: bool = False
    okx_rate_limit: int = 20  # запросов в секунду

    # Настройки базы данных
    database_enabled: bool = True
    database_url: str | None = None
    database_pool_size: int = 10
    database_timeout: float = 30.0

    # Настройки кэширования
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    cache_max_size: int = 1000

    # Настройки уведомлений
    notifications_enabled: bool = False
    slack_webhook_url: str | None = None
    email_smtp_server: str | None = None
    email_smtp_port: int = 587
    email_username: str | None = None
    email_password: str | None = None
    email_from: str | None = None
    email_to: list[str] = field(default_factory=list)

    # Настройки логирования
    enable_logging: bool = True
    log_level: str = "INFO"
    log_performance: bool = True

    # Настройки мониторинга
    enable_metrics: bool = True
    metrics_interval_seconds: int = 60

    # Настройки обработки
    enable_parallel_processing: bool = True
    enable_error_recovery: bool = True

    # Пороги и лимиты
    max_timeframes_per_request: int = 10
    min_data_points: int = 5
    max_processing_time_seconds: float = 60.0

    # Настройки алертов
    enable_alerts: bool = False
    alert_threshold_errors: int = 5
    alert_threshold_latency: float = 10.0

    @classmethod
    def from_yaml(cls, config_path: str) -> "IntegrationConfig":
        """Загрузка конфигурации из YAML файла"""
        import yaml

        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data.get("integration", {}))

    @classmethod
    def default(cls) -> "IntegrationConfig":
        """Создание конфигурации по умолчанию"""
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "max_workers": self.max_workers,
            "timeout_seconds": self.timeout_seconds,
            "retry_attempts": self.retry_attempts,
            "retry_delay_seconds": self.retry_delay_seconds,
            "okx_enabled": self.okx_enabled,
            "okx_sandbox": self.okx_sandbox,
            "okx_rate_limit": self.okx_rate_limit,
            "database_enabled": self.database_enabled,
            "database_pool_size": self.database_pool_size,
            "database_timeout": self.database_timeout,
            "cache_enabled": self.cache_enabled,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "cache_max_size": self.cache_max_size,
            "notifications_enabled": self.notifications_enabled,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level,
            "log_performance": self.log_performance,
            "enable_metrics": self.enable_metrics,
            "metrics_interval_seconds": self.metrics_interval_seconds,
            "enable_parallel_processing": self.enable_parallel_processing,
            "enable_error_recovery": self.enable_error_recovery,
            "max_timeframes_per_request": self.max_timeframes_per_request,
            "min_data_points": self.min_data_points,
            "max_processing_time_seconds": self.max_processing_time_seconds,
            "enable_alerts": self.enable_alerts,
            "alert_threshold_errors": self.alert_threshold_errors,
            "alert_threshold_latency": self.alert_threshold_latency,
        }
