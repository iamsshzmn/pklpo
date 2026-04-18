"""
MTF Database Models

Data models for working with the MTF system database.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class RegimeType(StrEnum):
    """Market regime types"""

    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    FLAT = "flat"


class AccelerationType(StrEnum):
    """Acceleration types"""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConsensusType(StrEnum):
    """Consensus types"""

    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"
    CONFLICTED = "conflicted"


class ConfidenceLevel(StrEnum):
    """Confidence levels"""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class ProcessingStatus(StrEnum):
    """Processing statuses"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ProcessingStage(StrEnum):
    """Processing stages"""

    CONTEXT = "context"
    TRIGGERS = "triggers"
    CONSENSUS = "consensus"
    INTEGRATION = "integration"
    COMPLETED = "completed"


@dataclass
class MTFContextRecord:
    """Context module result record"""

    id: int | None = None
    symbol: str = ""
    timeframe: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # Market regime analysis results
    dominant_regime: RegimeType = RegimeType.FLAT
    regime_confidence: float = 0.0

    # Overall score
    overall_score: float = 0.0

    # Detailed per-timeframe results
    timeframe_results: dict[str, Any] = field(default_factory=dict)

    # Metadata
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    processing_time_ms: int | None = None
    created_at: datetime | None = None


@dataclass
class MTFTriggersRecord:
    """Triggers module result record"""

    id: int | None = None
    symbol: str = ""
    timeframe: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # Core probabilities
    overall_p_up: float = 0.0
    overall_p_down: float = 0.0

    # Acceleration
    acceleration_type: AccelerationType = AccelerationType.NEUTRAL
    acceleration_strength: float = 0.0

    # Micro-filters
    micro_ok: bool = False
    micro_filter_score: float = 0.0

    # Detailed per-timeframe results
    timeframe_results: dict[str, Any] = field(default_factory=dict)

    # Metadata
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    processing_time_ms: int | None = None
    created_at: datetime | None = None


@dataclass
class MTFConsensusRecord:
    """Consensus module result record"""

    id: int | None = None
    symbol: str = ""
    timeframes: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    # Core consensus results
    consensus_type: ConsensusType = ConsensusType.NEUTRAL
    confidence_level: ConfidenceLevel = ConfidenceLevel.VERY_LOW
    consensus_score: float = 0.0

    # Weights and metrics
    context_weight: float = 0.0
    triggers_weight: float = 0.0
    coverage_ratio: float = 0.0
    disagreement_ratio: float = 0.0

    # Veto logic
    veto_applied: bool = False
    veto_reasons: list[str] = field(default_factory=list)

    # Detailed results
    timeframe_consensus: dict[str, Any] = field(default_factory=dict)
    evidence_summary: dict[str, Any] = field(default_factory=dict)

    # Metadata
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    processing_time_ms: int | None = None
    created_at: datetime | None = None


@dataclass
class MTFPipelineRecord:
    """Pipeline module result record"""

    id: int | None = None
    symbol: str = ""
    timeframes: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    # Processing status
    status: ProcessingStatus = ProcessingStatus.FAILED
    processing_stage: ProcessingStage = ProcessingStage.CONTEXT

    # Module result references
    context_id: int | None = None
    triggers_id: int | None = None
    consensus_id: int | None = None

    # Metadata
    total_processing_time_ms: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass
class MTFIntegrationRecord:
    """Integration module result record"""

    id: int | None = None
    symbol: str = ""
    timeframes: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    # Integration status
    status: ProcessingStatus = ProcessingStatus.FAILED

    # External system integration results
    okx_success: bool = False
    database_success: bool = False
    notifications_sent: bool = False

    # Metadata
    processing_time_ms: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass
class MTFQueryFilters:
    """Filters for MTF data queries"""

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
    """Aggregated MTF analysis result"""

    symbol: str
    timeframes: list[str]
    timestamp: datetime

    # Context results
    dominant_regime: RegimeType
    regime_confidence: float
    context_score: float

    # Triggers results
    overall_p_up: float
    overall_p_down: float
    acceleration_type: AccelerationType
    micro_ok: bool

    # Consensus results
    consensus_type: ConsensusType
    confidence_level: ConfidenceLevel
    consensus_score: float
    veto_applied: bool

    # Integration results
    integration_status: ProcessingStatus

    # Metadata
    total_processing_time_ms: int
    created_at: datetime
