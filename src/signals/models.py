"""
Модели данных для модуля Signals (Фаза 4)

Основные контракты:
- Decision: торговое решение с полным контрактом
- SignalCandidate: кандидат на торговый сигнал
- SignalLive: активный торговый сигнал
- SignalHistory: история исполненных сигналов
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import pandas as pd


class SignalStatus(Enum):
    """Статусы сигналов"""

    PENDING = "pending"  # Ожидает валидации
    VALIDATED = "validated"  # Прошел валидацию
    REJECTED = "rejected"  # Отклонен валидацией
    LIVE = "live"  # Активный сигнал
    EXPIRED = "expired"  # Истек по времени
    CANCELLED = "cancelled"  # Отменен вручную
    EXECUTED = "executed"  # Исполнен
    FAILED = "failed"  # Не удалось исполнить


class SignalHorizon(Enum):
    """Временные горизонты сигналов"""

    INTRADAY = "intraday"  # Внутридневная торговля
    SWING = "swing"  # Свинг-торговля
    WEEK = "week"  # Недельная торговля


class SignalSide(Enum):
    """Направления торговли"""

    LONG = "long"  # Покупка
    SHORT = "short"  # Продажа
    FLAT = "flat"  # Закрытие позиции


@dataclass
class Decision:
    """
    Основной контракт торгового решения

    Полный контракт согласно task project.md:
    - symbol_id, ts, horizon, side, entry, stop, take, ttl_sec
    - confidence (0..1), expected_r (после fees/slippage/funding)
    - rationale[], algo_version, params_hash, run_id
    """

    symbol_id: int
    ts: pd.Timestamp
    horizon: SignalHorizon
    side: SignalSide
    entry: float
    stop: float
    take: float
    ttl_sec: int
    confidence: float  # 0..1
    expected_r: float  # после fees/slippage/funding
    rationale: list[str]
    algo_version: str
    params_hash: str
    run_id: str

    def __post_init__(self):
        """Валидация после создания"""
        if not 0 <= self.confidence <= 1:
            raise ValueError(
                f"Confidence must be between 0 and 1, got {self.confidence}"
            )

        if self.entry <= 0:
            raise ValueError(f"Entry price must be positive, got {self.entry}")

        if self.stop <= 0:
            raise ValueError(f"Stop price must be positive, got {self.stop}")

        if self.take <= 0:
            raise ValueError(f"Take price must be positive, got {self.take}")

        if self.ttl_sec <= 0:
            raise ValueError(f"TTL must be positive, got {self.ttl_sec}")

        # Проверка логики цен
        if self.side == SignalSide.LONG:
            if self.stop >= self.entry:
                raise ValueError(
                    f"Long position: stop ({self.stop}) must be < entry ({self.entry})"
                )
            if self.take <= self.entry:
                raise ValueError(
                    f"Long position: take ({self.take}) must be > entry ({self.entry})"
                )
        elif self.side == SignalSide.SHORT:
            if self.stop <= self.entry:
                raise ValueError(
                    f"Short position: stop ({self.stop}) must be > entry ({self.entry})"
                )
            if self.take >= self.entry:
                raise ValueError(
                    f"Short position: take ({self.take}) must be < entry ({self.entry})"
                )


@dataclass
class ValidationResult:
    """Результат валидации сигнала"""

    is_valid: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    market_conditions: dict[str, Any] = field(default_factory=dict)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=dict)
    validated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SignalCandidate:
    """
    Кандидат на торговый сигнал

    Создается из Decision и проходит валидацию
    """

    id: UUID = field(default_factory=uuid4)
    decision: Decision = None
    status: SignalStatus = SignalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    validation_results: ValidationResult | None = None

    def __post_init__(self):
        if self.decision is None:
            raise ValueError("Decision is required for SignalCandidate")


@dataclass
class SignalLive:
    """
    Активный торговый сигнал

    Создается из валидированного SignalCandidate
    """

    candidate_id: UUID
    decision: Decision
    id: UUID = field(default_factory=uuid4)
    status: SignalStatus = SignalStatus.LIVE
    activated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    executed_at: datetime | None = None
    execution_metrics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.expires_at is None:
            # Автоматически устанавливаем время истечения на основе TTL
            self.expires_at = self.activated_at + pd.Timedelta(
                seconds=self.decision.ttl_sec
            )


@dataclass
class SignalHistory:
    """
    История исполненных сигналов

    Создается при завершении SignalLive
    """

    live_id: UUID
    decision: Decision
    status: SignalStatus
    activated_at: datetime
    expires_at: datetime
    executed_at: datetime
    actual_r: float  # Фактическая доходность
    id: UUID = field(default_factory=uuid4)
    execution_metrics: dict[str, Any] = field(default_factory=dict)
    performance_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalMetrics:
    """Метрики производительности сигналов"""

    total_generated: int = 0
    total_validated: int = 0
    total_promoted: int = 0
    total_executed: int = 0
    total_failed: int = 0
    validation_pass_rate: float = 0.0
    promotion_rate: float = 0.0
    execution_success_rate: float = 0.0
    avg_expected_r: float = 0.0
    avg_actual_r: float = 0.0
    avg_confidence: float = 0.0
    avg_execution_time_sec: float = 0.0


@dataclass
class SignalConfig:
    """Конфигурация модуля Signals"""

    # Валидация
    min_confidence: float = 0.6
    max_ttl_sec: int = 86400  # 24 часа
    min_expected_r: float = 0.01  # 1%

    # Риск-менеджмент
    max_concurrent_signals: int = 10
    max_daily_signals: int = 50
    cooldown_sec: int = 300  # 5 минут между сигналами

    # Market conditions
    min_liquidity_usdt: float = 10000.0
    max_spread_bps: float = 50.0  # 0.5%
    min_volume_24h_usdt: float = 100000.0

    # Data quality
    max_data_age_sec: int = 300  # 5 минут
    min_data_quality_score: float = 0.8

    # Alerts
    enable_alerts: bool = True
    alert_channels: list[str] = field(default_factory=lambda: ["slack", "telegram"])

    def validate(self):
        """Валидация конфигурации"""
        if not 0 <= self.min_confidence <= 1:
            raise ValueError(
                f"min_confidence must be between 0 and 1, got {self.min_confidence}"
            )

        if self.max_ttl_sec <= 0:
            raise ValueError(f"max_ttl_sec must be positive, got {self.max_ttl_sec}")

        if self.max_concurrent_signals <= 0:
            raise ValueError(
                f"max_concurrent_signals must be positive, got {self.max_concurrent_signals}"
            )


# Типы для API
DecisionRequest = dict[str, Any]
SignalCandidateRequest = dict[str, Any]
SignalLiveRequest = dict[str, Any]
ValidationRequest = dict[str, Any]
MetricsRequest = dict[str, Any]
