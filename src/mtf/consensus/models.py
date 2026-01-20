"""
Модели данных для Consensus модуля
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ValidationStatus(Enum):
    """Статусы валидации"""

    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


@dataclass
class ValidationResult:
    """Результат валидации"""

    status: ValidationStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class ConsensusType(Enum):
    """Типы консенсуса"""

    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"
    CONFLICTED = "conflicted"


class ConfidenceLevel(Enum):
    """Уровни уверенности"""

    VERY_HIGH = "very_high"  # 0.9+
    HIGH = "high"  # 0.7-0.9
    MEDIUM = "medium"  # 0.5-0.7
    LOW = "low"  # 0.3-0.5
    VERY_LOW = "very_low"  # 0.0-0.3


@dataclass
class ConsensusData:
    """Данные для консенсуса"""

    symbol: str
    timestamp: datetime
    context_score: float
    triggers_score: float
    timeframe_weights: dict[str, float]
    confidence: float
    consensus_type: ConsensusType
    confidence_level: ConfidenceLevel
    supporting_factors: list[str] = field(default_factory=list)
    conflicting_factors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    """Результат консенсуса"""

    symbol: str
    timestamp: datetime
    consensus_type: ConsensusType
    confidence_level: ConfidenceLevel
    final_score: float
    context_weight: float
    triggers_weight: float
    timeframe_breakdown: dict[str, dict[str, float]]
    supporting_evidence: list[str]
    conflicting_evidence: list[str]
    warnings: list[str] = field(default_factory=list)
    is_valid: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_bullish(self) -> bool:
        """Проверка на бычий консенсус"""
        return self.consensus_type in [
            ConsensusType.BULLISH,
            ConsensusType.STRONG_BULLISH,
        ]

    @property
    def is_bearish(self) -> bool:
        """Проверка на медвежий консенсус"""
        return self.consensus_type in [
            ConsensusType.BEARISH,
            ConsensusType.STRONG_BEARISH,
        ]

    @property
    def is_neutral(self) -> bool:
        """Проверка на нейтральный консенсус"""
        return self.consensus_type == ConsensusType.NEUTRAL

    @property
    def is_conflicted(self) -> bool:
        """Проверка на конфликтный консенсус"""
        return self.consensus_type == ConsensusType.CONFLICTED

    @property
    def net_score(self) -> float:
        """Чистый счет консенсуса"""
        return self.final_score


@dataclass
class ConsensusRequest:
    """Запрос на построение консенсуса"""

    symbol: str
    timeframes: list[str]
    context_data: dict[str, Any] | None = None
    triggers_data: dict[str, Any] | None = None
    timestamp: datetime | None = None
    custom_weights: dict[str, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusMetrics:
    """Метрики консенсуса"""

    calculation_time: float
    symbols_processed: int
    symbols_successful: int
    symbols_failed: int
    consensus_distribution: dict[ConsensusType, int]
    confidence_distribution: dict[ConfidenceLevel, int]
    average_confidence: float
    conflict_rate: float

    @property
    def success_rate(self) -> float:
        """Процент успешных символов"""
        if self.symbols_processed == 0:
            return 0.0
        return self.symbols_successful / self.symbols_processed


@dataclass
class ConsensusConfig:
    """Конфигурация консенсуса"""

    # Веса для агрегации
    context_weight: float = 0.4
    triggers_weight: float = 0.6

    # Пороги для классификации
    strong_bullish_threshold: float = 0.7
    bullish_threshold: float = 0.3
    bearish_threshold: float = -0.3
    strong_bearish_threshold: float = -0.7

    # Пороги уверенности
    very_high_confidence: float = 0.9
    high_confidence: float = 0.7
    medium_confidence: float = 0.5
    low_confidence: float = 0.3

    # Настройки конфликтов
    conflict_threshold: float = 0.2  # Если разница между context и triggers > threshold
    min_confidence_for_consensus: float = 0.4

    # Веса таймфреймов
    timeframe_weights: dict[str, float] = field(
        default_factory=lambda: {
            "15m": 1.0,
            "5m": 0.8,
            "1m": 0.6,
            "1H": 1.2,
            "4H": 1.5,
            "1D": 2.0,
        }
    )

    # Настройки валидации
    min_data_points: int = 5
    max_age_hours: int = 24

    # Настройки агрегации
    enable_timeframe_aggregation: bool = True
    enable_confidence_boost: bool = True
    confidence_boost_factor: float = 1.2

    # Настройки логирования
    enable_logging: bool = True
    log_level: str = "INFO"

    # Настройки кэширования
    cache_enabled: bool = False
    cache_ttl_seconds: int = 300

    # Настройки производительности
    max_workers: int = 4
    timeout_seconds: float = 30.0

    def get_timeframe_weight(self, timeframe: str) -> float:
        """Получить вес таймфрейма"""
        return self.timeframe_weights.get(timeframe, 0.5)

    def get_consensus_type(self, score: float) -> ConsensusType:
        """Определить тип консенсуса по счету"""
        if score >= self.strong_bullish_threshold:
            return ConsensusType.STRONG_BULLISH
        if score >= self.bullish_threshold:
            return ConsensusType.BULLISH
        if score <= self.strong_bearish_threshold:
            return ConsensusType.STRONG_BEARISH
        if score <= self.bearish_threshold:
            return ConsensusType.BEARISH
        return ConsensusType.NEUTRAL

    def get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Определить уровень уверенности"""
        if confidence >= self.very_high_confidence:
            return ConfidenceLevel.VERY_HIGH
        if confidence >= self.high_confidence:
            return ConfidenceLevel.HIGH
        if confidence >= self.medium_confidence:
            return ConfidenceLevel.MEDIUM
        if confidence >= self.low_confidence:
            return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW

    @classmethod
    def default(cls) -> "ConsensusConfig":
        """Создание конфигурации по умолчанию"""
        return cls()
