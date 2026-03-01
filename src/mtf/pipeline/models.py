"""
Data models for MTF Pipeline module
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd

from ..consensus.models import ConsensusResult
from ..context.models import ContextResult
from ..triggers.models import TriggersResult


class ProcessingStage(Enum):
    """Стадии обработки в pipeline"""

    INITIALIZED = "initialized"
    CONTEXT_BUILDING = "context_building"
    TRIGGERS_BUILDING = "triggers_building"
    CONSENSUS_BUILDING = "consensus_building"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStatus(Enum):
    """Статус pipeline"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineRequest:
    """Запрос на обработку pipeline"""

    symbol: str
    timeframes: list[str]
    features_data: dict[str, pd.DataFrame]
    context_config: dict[str, Any] | None = None
    triggers_config: dict[str, Any] | None = None
    consensus_config: dict[str, Any] | None = None
    request_id: str | None = None
    priority: int = 1
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Результат обработки pipeline"""

    request_id: str
    symbol: str
    timeframes: list[str]
    status: PipelineStatus
    processing_stage: ProcessingStage

    # Результаты компонентов
    context_result: ContextResult | None = None
    triggers_result: TriggersResult | None = None
    consensus_result: ConsensusResult | None = None

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
        """Проверка успешности обработки"""
        return self.status == PipelineStatus.COMPLETED and not self.errors

    @property
    def has_consensus(self) -> bool:
        """Проверка наличия консенсуса"""
        return self.consensus_result is not None and self.consensus_result.is_valid

    @property
    def final_consensus_type(self) -> str | None:
        """Получение финального типа консенсуса"""
        if self.consensus_result:
            return self.consensus_result.consensus_type.value
        return None

    @property
    def final_confidence_level(self) -> str | None:
        """Получение финального уровня уверенности"""
        if self.consensus_result:
            return self.consensus_result.confidence_level.value
        return None


@dataclass
class PipelineMetrics:
    """Метрики pipeline"""

    # Общие метрики
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cancelled_requests: int = 0

    # Временные метрики
    avg_processing_time: float = 0.0
    min_processing_time: float = 0.0
    max_processing_time: float = 0.0

    # Метрики по стадиям
    context_build_time: float = 0.0
    triggers_build_time: float = 0.0
    consensus_build_time: float = 0.0

    # Метрики по компонентам
    context_success_rate: float = 0.0
    triggers_success_rate: float = 0.0
    consensus_success_rate: float = 0.0

    # Метрики по символам
    symbols_processed: int = 0
    unique_symbols: int = 0

    # Метрики по таймфреймам
    timeframes_processed: int = 0
    avg_timeframes_per_request: float = 0.0

    # Ошибки
    total_errors: int = 0
    context_errors: int = 0
    triggers_errors: int = 0
    consensus_errors: int = 0

    # Кэш
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0


@dataclass
class PipelineConfig:
    """Конфигурация pipeline"""

    # Общие настройки
    max_workers: int = 4
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    # Настройки компонентов
    context_enabled: bool = True
    triggers_enabled: bool = True
    consensus_enabled: bool = True

    # Настройки кэширования
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    cache_max_size: int = 1000

    # Настройки логирования
    enable_logging: bool = True
    log_level: str = "INFO"
    log_performance: bool = True

    # Настройки мониторинга
    enable_metrics: bool = True
    metrics_interval_seconds: int = 60

    # Настройки обработки
    enable_parallel_processing: bool = True
    enable_timeframe_aggregation: bool = True
    enable_error_recovery: bool = True

    # Пороги и лимиты
    max_timeframes_per_request: int = 10
    min_data_points: int = 5
    max_processing_time_seconds: float = 60.0

    # Настройки уведомлений
    enable_notifications: bool = False
    notification_threshold_errors: int = 5

    @classmethod
    def from_yaml(cls, config_path: str) -> "PipelineConfig":
        """Загрузка конфигурации из YAML файла"""
        import yaml

        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        return cls(**config_data.get("pipeline", {}))

    @classmethod
    def default(cls) -> "PipelineConfig":
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
            "cache_enabled": self.cache_enabled,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "cache_max_size": self.cache_max_size,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level,
            "log_performance": self.log_performance,
            "enable_metrics": self.enable_metrics,
            "metrics_interval_seconds": self.metrics_interval_seconds,
            "enable_parallel_processing": self.enable_parallel_processing,
            "enable_timeframe_aggregation": self.enable_timeframe_aggregation,
            "enable_error_recovery": self.enable_error_recovery,
            "max_timeframes_per_request": self.max_timeframes_per_request,
            "min_data_points": self.min_data_points,
            "max_processing_time_seconds": self.max_processing_time_seconds,
            "enable_notifications": self.enable_notifications,
            "notification_threshold_errors": self.notification_threshold_errors,
        }
