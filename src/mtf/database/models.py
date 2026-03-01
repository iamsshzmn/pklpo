"""
MTF Database Models

Модели данных для работы с базой данных MTF системы.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RegimeType(str, Enum):
    """Типы режимов рынка"""

    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    FLAT = "flat"


class AccelerationType(str, Enum):
    """Типы ускорения"""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConsensusType(str, Enum):
    """Типы консенсуса"""

    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"
    CONFLICTED = "conflicted"


class ConfidenceLevel(str, Enum):
    """Уровни уверенности"""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class ProcessingStatus(str, Enum):
    """Статусы обработки"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ProcessingStage(str, Enum):
    """Этапы обработки"""

    CONTEXT = "context"
    TRIGGERS = "triggers"
    CONSENSUS = "consensus"
    INTEGRATION = "integration"
    COMPLETED = "completed"


@dataclass
class MTFContextRecord:
    """Запись результатов Context модуля"""

    id: int | None = None
    symbol: str = ""
    timeframe: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # Результаты анализа режима рынка
    dominant_regime: RegimeType = RegimeType.FLAT
    regime_confidence: float = 0.0

    # Общий score
    overall_score: float = 0.0

    # Детальные результаты по таймфреймам
    timeframe_results: dict[str, Any] = field(default_factory=dict)

    # Метаданные
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    processing_time_ms: int | None = None
    created_at: datetime | None = None


@dataclass
class MTFTriggersRecord:
    """Запись результатов Triggers модуля"""

    id: int | None = None
    symbol: str = ""
    timeframe: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # Основные вероятности
    overall_p_up: float = 0.0
    overall_p_down: float = 0.0

    # Ускорение
    acceleration_type: AccelerationType = AccelerationType.NEUTRAL
    acceleration_strength: float = 0.0

    # Микро-фильтры
    micro_ok: bool = False
    micro_filter_score: float = 0.0

    # Детальные результаты по таймфреймам
    timeframe_results: dict[str, Any] = field(default_factory=dict)

    # Метаданные
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    processing_time_ms: int | None = None
    created_at: datetime | None = None


@dataclass
class MTFConsensusRecord:
    """Запись результатов Consensus модуля"""

    id: int | None = None
    symbol: str = ""
    timeframes: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    # Основные результаты консенсуса
    consensus_type: ConsensusType = ConsensusType.NEUTRAL
    confidence_level: ConfidenceLevel = ConfidenceLevel.VERY_LOW
    consensus_score: float = 0.0

    # Веса и метрики
    context_weight: float = 0.0
    triggers_weight: float = 0.0
    coverage_ratio: float = 0.0
    disagreement_ratio: float = 0.0

    # Veto логика
    veto_applied: bool = False
    veto_reasons: list[str] = field(default_factory=list)

    # Детальные результаты
    timeframe_consensus: dict[str, Any] = field(default_factory=dict)
    evidence_summary: dict[str, Any] = field(default_factory=dict)

    # Метаданные
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    processing_time_ms: int | None = None
    created_at: datetime | None = None


@dataclass
class MTFPipelineRecord:
    """Запись результатов Pipeline модуля"""

    id: int | None = None
    symbol: str = ""
    timeframes: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    # Статус обработки
    status: ProcessingStatus = ProcessingStatus.FAILED
    processing_stage: ProcessingStage = ProcessingStage.CONTEXT

    # Ссылки на результаты модулей
    context_id: int | None = None
    triggers_id: int | None = None
    consensus_id: int | None = None

    # Метаданные
    total_processing_time_ms: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass
class MTFIntegrationRecord:
    """Запись результатов Integration модуля"""

    id: int | None = None
    symbol: str = ""
    timeframes: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    # Статус интеграции
    status: ProcessingStatus = ProcessingStatus.FAILED

    # Результаты интеграции с внешними системами
    okx_success: bool = False
    database_success: bool = False
    notifications_sent: bool = False

    # Метаданные
    processing_time_ms: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass
class MTFQueryFilters:
    """Фильтры для запросов к MTF данным"""

    symbols: list[str] | None = None
    timeframes: list[str] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    consensus_types: list[ConsensusType] | None = None
    confidence_levels: list[ConfidenceLevel] | None = None
    regimes: list[RegimeType] | None = None
    acceleration_types: list[AccelerationType] | None = None
    valid_only: bool = True
    limit: int | None = None
    offset: int | None = None


@dataclass
class MTFAggregatedResult:
    """Агрегированный результат MTF анализа"""

    symbol: str
    timeframes: list[str]
    timestamp: datetime

    # Context результаты
    dominant_regime: RegimeType
    regime_confidence: float
    context_score: float

    # Triggers результаты
    overall_p_up: float
    overall_p_down: float
    acceleration_type: AccelerationType
    micro_ok: bool

    # Consensus результаты
    consensus_type: ConsensusType
    confidence_level: ConfidenceLevel
    consensus_score: float
    veto_applied: bool

    # Integration результаты
    integration_status: ProcessingStatus

    # Метаданные
    total_processing_time_ms: int
    created_at: datetime
