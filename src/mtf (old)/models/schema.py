#!/usr/bin/env python3
"""
MTF Database Schema

Схема данных для MTF модуля с версионированием, контрактами и поддержкой качества данных.
Включает таблицы для context, triggers, consensus и операционных метрик.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SignalSide(Enum):
    """Стороны сигнала"""

    LONG = 1
    SHORT = -1
    FLAT = 0


class QualityStatus(Enum):
    """Статусы качества данных"""

    EXCELLENT = "excellent"
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RunStatus(Enum):
    """Статусы выполнения"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Основные MTF таблицы
# ============================================================================


class MTFContext(Base):
    """Контекстные данные MTF"""

    __tablename__ = "mtf_context"

    # Основные поля
    id = Column(Integer, primary_key=True)
    run_id = Column(String(36), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Контекстные метрики
    score = Column(Float, nullable=False)
    valid = Column(Boolean, nullable=False, default=True)
    regime = Column(String(20), nullable=True)  # trend_bull, trend_bear, flat, volatile

    # Качество данных
    data_quality_status = Column(String(20), nullable=False, default="unknown")
    data_age_minutes = Column(Float, nullable=True)
    valid_rate = Column(Float, nullable=True)
    nan_rate = Column(Float, nullable=True)

    # Версионирование
    schema_version = Column(String(10), nullable=False, default="v1")
    algo_version = Column(String(20), nullable=False, default="1.0.0")
    params_hash = Column(String(16), nullable=False)

    # Метаданные
    features_json = Column(JSON, nullable=True)
    warnings = Column(ARRAY(String), nullable=True)
    errors = Column(ARRAY(String), nullable=True)

    # Временные метки
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Индексы
    __table_args__ = (
        Index("idx_mtf_context_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
        Index("idx_mtf_context_run_id", "run_id"),
        Index("idx_mtf_context_quality", "data_quality_status"),
        UniqueConstraint(
            "symbol", "timeframe", "timestamp", "run_id", name="uq_mtf_context_unique"
        ),
    )


class MTFTriggers(Base):
    """Триггерные данные MTF"""

    __tablename__ = "mtf_triggers"

    # Основные поля
    id = Column(Integer, primary_key=True)
    run_id = Column(String(36), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Триггерные метрики
    p_up = Column(Float, nullable=False)  # Вероятность роста
    p_down = Column(Float, nullable=False)  # Вероятность падения
    accel = Column(Integer, nullable=True)  # Ускорение
    micro_ok = Column(Boolean, nullable=True)  # Микро-качество входа

    # Качество данных
    data_quality_status = Column(String(20), nullable=False, default="unknown")
    lookahead_guard = Column(Boolean, nullable=False, default=True)
    future_data_detected = Column(Boolean, nullable=False, default=False)

    # Версионирование
    schema_version = Column(String(10), nullable=False, default="v1")
    algo_version = Column(String(20), nullable=False, default="1.0.0")
    params_hash = Column(String(16), nullable=False)

    # Метаданные
    features_json = Column(JSON, nullable=True)
    warnings = Column(ARRAY(String), nullable=True)
    errors = Column(ARRAY(String), nullable=True)

    # Временные метки
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Индексы
    __table_args__ = (
        Index("idx_mtf_triggers_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
        Index("idx_mtf_triggers_run_id", "run_id"),
        Index("idx_mtf_triggers_quality", "data_quality_status"),
        UniqueConstraint(
            "symbol", "timeframe", "timestamp", "run_id", name="uq_mtf_triggers_unique"
        ),
    )


class MTFConsensus(Base):
    """Консенсусные данные MTF"""

    __tablename__ = "mtf_consensus"

    # Основные поля
    id = Column(Integer, primary_key=True)
    run_id = Column(String(36), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    horizon = Column(String(20), nullable=False, index=True)  # intraday, swing, week
    timestamp = Column(DateTime, nullable=False, index=True)

    # Консенсусные метрики
    side = Column(Integer, nullable=False)  # 1=long, -1=short, 0=flat
    strength = Column(Float, nullable=False)  # Сила сигнала
    coverage = Column(Float, nullable=False)  # Покрытие таймфреймов
    disagreement_score = Column(Float, nullable=True)  # Уровень разногласий

    # Качество данных
    data_quality_status = Column(String(20), nullable=False, default="unknown")
    consensus_confidence = Column(Float, nullable=True)

    # Версионирование
    schema_version = Column(String(10), nullable=False, default="v1")
    algo_version = Column(String(20), nullable=False, default="1.0.0")
    params_hash = Column(String(16), nullable=False)

    # Метаданные
    reasons = Column(ARRAY(String), nullable=True)  # Причины решения
    timeframe_votes = Column(JSON, nullable=True)  # Голоса по таймфреймам
    warnings = Column(ARRAY(String), nullable=True)
    errors = Column(ARRAY(String), nullable=True)

    # Временные метки
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Индексы
    __table_args__ = (
        Index("idx_mtf_consensus_symbol_horizon_ts", "symbol", "horizon", "timestamp"),
        Index("idx_mtf_consensus_run_id", "run_id"),
        Index("idx_mtf_consensus_side", "side"),
        Index("idx_mtf_consensus_strength", "strength"),
        UniqueConstraint(
            "symbol", "horizon", "timestamp", "run_id", name="uq_mtf_consensus_unique"
        ),
    )


# ============================================================================
# Операционные таблицы
# ============================================================================


class MTFRuns(Base):
    """Записи выполнения MTF операций"""

    __tablename__ = "mtf_runs"

    # Основные поля
    run_id = Column(String(36), primary_key=True)
    source = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running")

    # Версионирование
    version = Column(String(20), nullable=False, default="1.0.0")
    schema_version = Column(String(10), nullable=False, default="v1")
    params_hash = Column(String(16), nullable=False)
    env_hash = Column(String(16), nullable=False)
    git_sha = Column(String(40), nullable=True)

    # Временные метки
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # Метрики
    rows_processed = Column(Integer, nullable=False, default=0)
    rows_written = Column(Integer, nullable=False, default=0)
    errors_count = Column(Integer, nullable=False, default=0)
    warnings_count = Column(Integer, nullable=False, default=0)

    # Метаданные
    metadata = Column(JSON, nullable=True)
    steps = Column(JSON, nullable=True)  # Шаги выполнения
    error_message = Column(Text, nullable=True)

    # Индексы
    __table_args__ = (
        Index("idx_mtf_runs_source", "source"),
        Index("idx_mtf_runs_status", "status"),
        Index("idx_mtf_runs_started_at", "started_at"),
    )


class MTFDataQuality(Base):
    """Метрики качества данных"""

    __tablename__ = "mtf_data_quality"

    # Основные поля
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Статус качества
    status = Column(String(20), nullable=False)

    # Метрики свежести
    data_age_minutes = Column(Float, nullable=True)
    last_update = Column(DateTime, nullable=True)

    # Метрики валидности
    total_rows = Column(Integer, nullable=False, default=0)
    valid_rows = Column(Integer, nullable=False, default=0)
    nan_count = Column(Integer, nullable=False, default=0)
    valid_rate = Column(Float, nullable=True)
    nan_rate = Column(Float, nullable=True)

    # Аномалии
    volume_spike = Column(Float, nullable=True)
    spread_widening = Column(Float, nullable=True)
    price_gap = Column(Float, nullable=True)

    # Look-ahead защита
    lookahead_guard = Column(Boolean, nullable=False, default=True)
    future_data_detected = Column(Boolean, nullable=False, default=False)

    # Предупреждения и ошибки
    warnings = Column(ARRAY(String), nullable=True)
    errors = Column(ARRAY(String), nullable=True)

    # Временные метки
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Индексы
    __table_args__ = (
        Index("idx_mtf_data_quality_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
        Index("idx_mtf_data_quality_status", "status"),
        UniqueConstraint(
            "symbol", "timeframe", "timestamp", name="uq_mtf_data_quality_unique"
        ),
    )


class MTFAlerts(Base):
    """История алертов"""

    __tablename__ = "mtf_alerts"

    # Основные поля
    id = Column(Integer, primary_key=True)
    level = Column(
        String(20), nullable=False, index=True
    )  # info, warning, critical, error
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    source = Column(String(50), nullable=False, index=True)

    # Метаданные
    metadata = Column(JSON, nullable=True)

    # Временные метки
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Индексы
    __table_args__ = (
        Index("idx_mtf_alerts_level", "level"),
        Index("idx_mtf_alerts_source", "source"),
        Index("idx_mtf_alerts_timestamp", "timestamp"),
    )


# ============================================================================
# Торговые таблицы (для будущего расширения)
# ============================================================================


class MTFSignals(Base):
    """Торговые сигналы"""

    __tablename__ = "mtf_signals"

    # Основные поля
    id = Column(Integer, primary_key=True)
    run_id = Column(String(36), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Сигнал
    horizon = Column(String(20), nullable=False, index=True)
    side = Column(Integer, nullable=False)  # 1=long, -1=short, 0=flat
    confidence = Column(Float, nullable=False)

    # Позиция
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    position_size = Column(Float, nullable=True)

    # Временные ограничения
    ttl_hours = Column(Integer, nullable=True)
    time_stop = Column(DateTime, nullable=True)

    # Статус
    status = Column(
        String(20), nullable=False, default="active"
    )  # active, filled, cancelled, expired

    # Версионирование
    algo_version = Column(String(20), nullable=False, default="1.0.0")
    params_hash = Column(String(16), nullable=False)

    # Метаданные
    reasoning = Column(ARRAY(String), nullable=True)
    risk_level = Column(String(20), nullable=True)

    # Временные метки
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Индексы
    __table_args__ = (
        Index("idx_mtf_signals_symbol_ts", "symbol", "timestamp"),
        Index("idx_mtf_signals_run_id", "run_id"),
        Index("idx_mtf_signals_status", "status"),
        Index("idx_mtf_signals_side", "side"),
        UniqueConstraint("symbol", "timestamp", "run_id", name="uq_mtf_signals_unique"),
    )


# ============================================================================
# Утилиты для работы со схемой
# ============================================================================


def get_table_names() -> list[str]:
    """Получить список всех таблиц MTF"""
    return [
        "mtf_context",
        "mtf_triggers",
        "mtf_consensus",
        "mtf_runs",
        "mtf_data_quality",
        "mtf_alerts",
        "mtf_signals",
    ]


def get_schema_version() -> str:
    """Получить текущую версию схемы"""
    return "v1"


def get_migration_scripts() -> dict[str, str]:
    """Получить скрипты миграции"""
    return {
        "v1": """
        -- Создание таблиц MTF v1
        CREATE TABLE IF NOT EXISTS mtf_context (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            score FLOAT NOT NULL,
            valid BOOLEAN NOT NULL DEFAULT TRUE,
            regime VARCHAR(20),
            data_quality_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            data_age_minutes FLOAT,
            valid_rate FLOAT,
            nan_rate FLOAT,
            schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
            algo_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            params_hash VARCHAR(16) NOT NULL,
            features_json JSONB,
            warnings TEXT[],
            errors TEXT[],
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS mtf_triggers (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            p_up FLOAT NOT NULL,
            p_down FLOAT NOT NULL,
            accel INTEGER,
            micro_ok BOOLEAN,
            data_quality_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            lookahead_guard BOOLEAN NOT NULL DEFAULT TRUE,
            future_data_detected BOOLEAN NOT NULL DEFAULT FALSE,
            schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
            algo_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            params_hash VARCHAR(16) NOT NULL,
            features_json JSONB,
            warnings TEXT[],
            errors TEXT[],
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS mtf_consensus (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            horizon VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            side INTEGER NOT NULL,
            strength FLOAT NOT NULL,
            coverage FLOAT NOT NULL,
            disagreement_score FLOAT,
            data_quality_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            consensus_confidence FLOAT,
            schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
            algo_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            params_hash VARCHAR(16) NOT NULL,
            reasons TEXT[],
            timeframe_votes JSONB,
            warnings TEXT[],
            errors TEXT[],
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );

        -- Создание индексов
        CREATE INDEX IF NOT EXISTS idx_mtf_context_symbol_tf_ts ON mtf_context(symbol, timeframe, timestamp);
        CREATE INDEX IF NOT EXISTS idx_mtf_context_run_id ON mtf_context(run_id);
        CREATE INDEX IF NOT EXISTS idx_mtf_context_quality ON mtf_context(data_quality_status);

        CREATE INDEX IF NOT EXISTS idx_mtf_triggers_symbol_tf_ts ON mtf_triggers(symbol, timeframe, timestamp);
        CREATE INDEX IF NOT EXISTS idx_mtf_triggers_run_id ON mtf_triggers(run_id);
        CREATE INDEX IF NOT EXISTS idx_mtf_triggers_quality ON mtf_triggers(data_quality_status);

        CREATE INDEX IF NOT EXISTS idx_mtf_consensus_symbol_horizon_ts ON mtf_consensus(symbol, horizon, timestamp);
        CREATE INDEX IF NOT EXISTS idx_mtf_consensus_run_id ON mtf_consensus(run_id);
        CREATE INDEX IF NOT EXISTS idx_mtf_consensus_side ON mtf_consensus(side);
        CREATE INDEX IF NOT EXISTS idx_mtf_consensus_strength ON mtf_consensus(strength);

        -- Создание уникальных ограничений
        ALTER TABLE mtf_context ADD CONSTRAINT uq_mtf_context_unique
            UNIQUE (symbol, timeframe, timestamp, run_id);
        ALTER TABLE mtf_triggers ADD CONSTRAINT uq_mtf_triggers_unique
            UNIQUE (symbol, timeframe, timestamp, run_id);
        ALTER TABLE mtf_consensus ADD CONSTRAINT uq_mtf_consensus_unique
            UNIQUE (symbol, horizon, timestamp, run_id);
        """
    }


def validate_data_contract(data: dict[str, Any], table_name: str) -> list[str]:
    """Валидация контракта данных"""
    errors = []

    if table_name == "mtf_context":
        required_fields = ["run_id", "symbol", "timeframe", "timestamp", "score"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Отсутствует обязательное поле: {field}")

        if "score" in data and not isinstance(data["score"], int | float):
            errors.append("score должен быть числом")

        if "valid" in data and not isinstance(data["valid"], bool):
            errors.append("valid должен быть булевым значением")

    elif table_name == "mtf_triggers":
        required_fields = [
            "run_id",
            "symbol",
            "timeframe",
            "timestamp",
            "p_up",
            "p_down",
        ]
        for field in required_fields:
            if field not in data:
                errors.append(f"Отсутствует обязательное поле: {field}")

        if "p_up" in data and not (0 <= data["p_up"] <= 1):
            errors.append("p_up должен быть в диапазоне [0, 1]")

        if "p_down" in data and not (0 <= data["p_down"] <= 1):
            errors.append("p_down должен быть в диапазоне [0, 1]")

    elif table_name == "mtf_consensus":
        required_fields = [
            "run_id",
            "symbol",
            "horizon",
            "timestamp",
            "side",
            "strength",
            "coverage",
        ]
        for field in required_fields:
            if field not in data:
                errors.append(f"Отсутствует обязательное поле: {field}")

        if "side" in data and data["side"] not in [-1, 0, 1]:
            errors.append("side должен быть -1, 0 или 1")

        if "strength" in data and not (0 <= data["strength"] <= 1):
            errors.append("strength должен быть в диапазоне [0, 1]")

    return errors
