"""
Модели данных для Triggers модуля
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd


class ValidationStatus(Enum):
    """Статусы валидации"""

    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    INVALID = "invalid"


@dataclass
class ValidationResult:
    """Результат валидации"""

    status: ValidationStatus
    message: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AccelerationType(Enum):
    """Типы ускорения"""

    BULLISH = 1
    NEUTRAL = 0
    BEARISH = -1


class MicroFilterStatus(Enum):
    """Статусы микро-фильтра"""

    PASSED = "passed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class NoiseFilterType(Enum):
    """Типы фильтров шума"""

    CLUSTER_CONFIRMATION = "cluster_confirmation"
    VOLUME_FILTER = "volume_filter"
    VOLATILITY_FILTER = "volatility_filter"
    TIME_FILTER = "time_filter"


@dataclass
class TriggerData:
    """Данные триггера для одного таймфрейма"""

    symbol: str
    timeframe: str
    timestamp: datetime
    p_up: float  # Вероятность разворота вверх (0.0 - 1.0)
    p_down: float  # Вероятность разворота вниз (0.0 - 1.0)
    accel: AccelerationType  # Ускорение
    micro_ok: bool  # Прошел ли микро-фильтр
    anti_noise_score: float  # Оценка anti-noise фильтра (0.0 - 1.0)
    valid: bool
    confidence: float  # Уверенность в триггере (0.0 - 1.0)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Валидация после инициализации"""
        if not 0.0 <= self.p_up <= 1.0:
            raise ValueError(f"p_up must be between 0.0 and 1.0, got {self.p_up}")

        if not 0.0 <= self.p_down <= 1.0:
            raise ValueError(f"p_down must be between 0.0 and 1.0, got {self.p_down}")

        if not 0.0 <= self.anti_noise_score <= 1.0:
            raise ValueError(
                f"anti_noise_score must be between 0.0 and 1.0, got {self.anti_noise_score}"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

        if not isinstance(self.accel, AccelerationType):
            if isinstance(self.accel, int):
                self.accel = AccelerationType(self.accel)
            else:
                raise ValueError(f"Invalid acceleration type: {self.accel}")

    @property
    def net_probability(self) -> float:
        """Чистая вероятность (p_up - p_down)"""
        return self.p_up - self.p_down

    @property
    def dominant_direction(self) -> str:
        """Доминирующее направление"""
        if self.p_up > self.p_down + 0.1:
            return "bullish"
        if self.p_down > self.p_up + 0.1:
            return "bearish"
        return "neutral"

    @property
    def strength(self) -> str:
        """Сила триггера"""
        max_prob = max(self.p_up, self.p_down)
        if max_prob >= 0.8:
            return "very_strong"
        if max_prob >= 0.6:
            return "strong"
        if max_prob >= 0.4:
            return "moderate"
        return "weak"


@dataclass
class TriggersResult:
    """Результат построения триггеров"""

    symbol: str
    timestamp: datetime
    triggers: dict[str, TriggerData]  # timeframe -> TriggerData
    overall_p_up: float
    overall_p_down: float
    dominant_acceleration: AccelerationType
    micro_filter_passed: bool
    noise_filter_effectiveness: float
    valid: bool
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Валидация после инициализации"""
        if not 0.0 <= self.overall_p_up <= 1.0:
            raise ValueError(
                f"overall_p_up must be between 0.0 and 1.0, got {self.overall_p_up}"
            )

        if not 0.0 <= self.overall_p_down <= 1.0:
            raise ValueError(
                f"overall_p_down must be between 0.0 and 1.0, got {self.overall_p_down}"
            )

        if not 0.0 <= self.noise_filter_effectiveness <= 1.0:
            raise ValueError(
                f"noise_filter_effectiveness must be between 0.0 and 1.0, got {self.noise_filter_effectiveness}"
            )

        if not isinstance(self.dominant_acceleration, AccelerationType):
            if isinstance(self.dominant_acceleration, int):
                self.dominant_acceleration = AccelerationType(
                    self.dominant_acceleration
                )
            else:
                raise ValueError(
                    f"Invalid dominant acceleration type: {self.dominant_acceleration}"
                )

    @property
    def timeframes(self) -> list[str]:
        """Список таймфреймов в результате"""
        return list(self.triggers.keys())

    @property
    def valid_triggers(self) -> dict[str, TriggerData]:
        """Только валидные триггеры"""
        return {tf: trigger for tf, trigger in self.triggers.items() if trigger.valid}

    @property
    def has_errors(self) -> bool:
        """Есть ли ошибки в результате"""
        return len(self.errors) > 0

    @property
    def is_valid(self) -> bool:
        """Проверка валидности результата"""
        return self.valid

    @property
    def net_probability(self) -> float:
        """Общая чистая вероятность"""
        return self.overall_p_up - self.overall_p_down

    @property
    def dominant_direction(self) -> str:
        """Доминирующее направление"""
        if self.overall_p_up > self.overall_p_down + 0.1:
            return "bullish"
        if self.overall_p_down > self.overall_p_up + 0.1:
            return "bearish"
        return "neutral"

    def get_trigger_by_timeframe(self, timeframe: str) -> TriggerData | None:
        """Получить триггер по таймфрейму"""
        return self.triggers.get(timeframe)

    def get_acceleration_by_timeframe(self, timeframe: str) -> AccelerationType | None:
        """Получить ускорение по таймфрейму"""
        trigger = self.get_trigger_by_timeframe(timeframe)
        return trigger.accel if trigger else None


@dataclass
class TriggersRequest:
    """Запрос на построение триггеров"""

    symbol: str
    timeframes: list[str]
    timestamp: datetime | None = None
    context_data: dict[str, Any] | None = None
    features_data: dict[str, pd.DataFrame] | None = None
    config_overrides: dict[str, Any] | None = None

    def __post_init__(self):
        """Валидация после инициализации"""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")

        if not self.timeframes:
            raise ValueError("Timeframes list cannot be empty")

        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class TriggersMetrics:
    """Метрики для триггеров"""

    calculation_time: float
    timeframes_processed: int
    timeframes_successful: int
    timeframes_failed: int
    average_p_up: float
    average_p_down: float
    acceleration_distribution: dict[AccelerationType, int]
    micro_filter_pass_rate: float
    noise_filter_effectiveness: float

    @property
    def success_rate(self) -> float:
        """Процент успешных таймфреймов"""
        if self.timeframes_processed == 0:
            return 0.0
        return self.timeframes_successful / self.timeframes_processed

    @property
    def failure_rate(self) -> float:
        """Процент неудачных таймфреймов"""
        return 1.0 - self.success_rate


@dataclass
class ProbabilityComponents:
    """Компоненты расчета вероятностей"""

    momentum_factor: float
    volume_factor: float
    volatility_factor: float
    support_resistance_factor: float
    pattern_factor: float
    final_p_up: float
    final_p_down: float


@dataclass
class AccelerationAnalysis:
    """Анализ ускорения"""

    acceleration: AccelerationType
    strength: float
    duration: int  # Количество периодов
    confidence: float
    factors: list[str]


@dataclass
class MicroFilterResult:
    """Результат микро-фильтра"""

    status: MicroFilterStatus
    score: float
    factors: list[str]
    confidence: float


@dataclass
class NoiseFilterResult:
    """Результат фильтра шума"""

    filter_type: NoiseFilterType
    passed: bool
    score: float
    effectiveness: float
    metadata: dict[str, Any]


@dataclass
class TriggersConfig:
    """Конфигурация для построения триггеров"""

    # Пороги для вероятностей
    min_probability_threshold: float = 0.3
    max_probability_threshold: float = 0.9

    # Веса для компонентов вероятности
    momentum_weight: float = 0.3
    volume_weight: float = 0.2
    volatility_weight: float = 0.2
    support_resistance_weight: float = 0.15
    pattern_weight: float = 0.15

    # Настройки ускорения
    acceleration_threshold: float = 0.1
    min_acceleration_periods: int = 3

    # Настройки микро-фильтра
    micro_filter_threshold: float = 0.5
    micro_filter_factors: list[str] = field(
        default_factory=lambda: [
            "volume_confirmation",
            "momentum_consistency",
            "volatility_check",
        ]
    )

    # Настройки anti-noise фильтра
    noise_filter_threshold: float = 0.6
    cluster_confirmation_periods: int = 5
    volume_spike_threshold: float = 1.5

    # Настройки валидации
    min_data_points: int = 20
    max_age_hours: int = 24

    # Настройки агрегации
    timeframe_weights: dict[str, float] = field(
        default_factory=lambda: {"15m": 1.0, "5m": 0.8, "1m": 0.6}
    )

    def get_timeframe_weight(self, timeframe: str) -> float:
        """Получить вес таймфрейма"""
        return self.timeframe_weights.get(timeframe, 0.5)
