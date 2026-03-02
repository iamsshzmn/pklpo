"""
Модели данных для Context Builder
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd


class ValidationStatus(Enum):
    """Статусы валидации"""

    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    ERROR = "error"


class RegimeType(Enum):
    """Типы режимов рынка"""

    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class ReasonCode(Enum):
    """Коды причин для валидности контекста"""

    EMA_TREND_UP = "ema_trend_up"
    EMA_TREND_DOWN = "ema_trend_down"
    ADX_STRONG_TREND = "adx_strong_trend"
    ADX_WEAK_TREND = "adx_weak_trend"
    RSI_OVERSOLD = "rsi_oversold"
    RSI_OVERBOUGHT = "rsi_overbought"
    MACD_BULLISH = "macd_bullish"
    MACD_BEARISH = "macd_bearish"
    VOLUME_CONFIRMATION = "volume_confirmation"
    ATR_HIGH_VOLATILITY = "atr_high_volatility"
    ATR_LOW_VOLATILITY = "atr_low_volatility"
    INSUFFICIENT_DATA = "insufficient_data"
    CONFLICTING_SIGNALS = "conflicting_signals"


@dataclass
class ValidationResult:
    """Результат валидации"""

    status: ValidationStatus
    message: str
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]


@dataclass
class ContextData:
    """Данные контекста для одного таймфрейма"""

    symbol: str
    timeframe: str
    timestamp: datetime
    score: float  # -1.0 до 1.0
    valid: bool
    regime: RegimeType
    reason_codes: list[ReasonCode] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Валидация после инициализации"""
        if not -1.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be between -1.0 and 1.0, got {self.score}")

        if not isinstance(self.regime, RegimeType):
            if isinstance(self.regime, str):
                self.regime = RegimeType(self.regime)
            else:
                raise ValueError(f"Invalid regime type: {self.regime}")


@dataclass
class ContextResult:
    """Результат построения контекста"""

    symbol: str
    timestamp: datetime
    contexts: dict[str, ContextData]  # timeframe -> ContextData
    overall_score: float
    dominant_regime: RegimeType
    confidence: float
    valid: bool
    errors: list[str] = field(default_factory=list)
    validation_result: ValidationResult | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Валидация после инициализации"""
        if not -1.0 <= self.overall_score <= 1.0:
            raise ValueError(
                f"Overall score must be between -1.0 and 1.0, got {self.overall_score}"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

        if not isinstance(self.dominant_regime, RegimeType):
            if isinstance(self.dominant_regime, str):
                self.dominant_regime = RegimeType(self.dominant_regime)
            else:
                raise ValueError(
                    f"Invalid dominant regime type: {self.dominant_regime}"
                )

    @property
    def timeframes(self) -> list[str]:
        """Список таймфреймов в результате"""
        return list(self.contexts.keys())

    @property
    def valid_contexts(self) -> dict[str, ContextData]:
        """Только валидные контексты"""
        return {tf: ctx for tf, ctx in self.contexts.items() if ctx.valid}

    @property
    def has_errors(self) -> bool:
        """Есть ли ошибки в результате"""
        return len(self.errors) > 0

    @property
    def is_valid(self) -> bool:
        """Проверка валидности результата"""
        return self.valid

    def get_context_by_timeframe(self, timeframe: str) -> ContextData | None:
        """Получить контекст по таймфрейму"""
        return self.contexts.get(timeframe)

    def get_regime_by_timeframe(self, timeframe: str) -> RegimeType | None:
        """Получить режим по таймфрейму"""
        context = self.get_context_by_timeframe(timeframe)
        return context.regime if context else None

    def get_score_by_timeframe(self, timeframe: str) -> float | None:
        """Получить score по таймфрейму"""
        context = self.get_context_by_timeframe(timeframe)
        return context.score if context else None


@dataclass
class TrendScoreComponents:
    """Компоненты trend score"""

    ema_trend: float
    adx_strength: float
    rsi_momentum: float
    macd_signal: float
    volume_confirmation: float
    volatility_factor: float
    final_score: float


@dataclass
class RegimeAnalysis:
    """Анализ режима рынка"""

    regime: RegimeType
    confidence: float
    trend_strength: float
    volatility_level: float
    volume_profile: str
    timeframe_consistency: float
    reasoning: list[str]


@dataclass
class ContextRequest:
    """Запрос на построение контекста"""

    symbol: str
    timeframes: list[str]
    timestamp: datetime | None = None
    features_data: dict[str, pd.DataFrame] | None = None
    market_meta_data: dict[str, Any] | None = None
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
class ContextMetrics:
    """Метрики для контекста"""

    calculation_time: float
    timeframes_processed: int
    timeframes_successful: int
    timeframes_failed: int
    average_score: float
    regime_distribution: dict[RegimeType, int]
    reason_code_distribution: dict[ReasonCode, int]

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
class ContextConfig:
    """Конфигурация для построения контекста"""

    # Пороги для определения режимов
    trend_threshold: float = 0.3
    flat_threshold: float = 0.1

    # Веса для компонентов score
    ema_weight: float = 0.3
    adx_weight: float = 0.2
    rsi_weight: float = 0.2
    macd_weight: float = 0.2
    volume_weight: float = 0.1

    # Пороги для индикаторов
    adx_strong_trend: float = 25.0
    adx_weak_trend: float = 15.0
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    # Настройки валидации
    min_data_points: int = 20
    max_age_hours: int = 24

    # Настройки агрегации
    timeframe_weights: dict[str, float] = field(
        default_factory=lambda: {"1Dutc": 1.0, "4H": 0.8, "1H": 0.6, "15m": 0.4}
    )

    def get_timeframe_weight(self, timeframe: str) -> float:
        """Получить вес таймфрейма"""
        return self.timeframe_weights.get(timeframe, 0.5)
