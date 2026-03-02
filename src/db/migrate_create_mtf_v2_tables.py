#!/usr/bin/env python3
"""
Миграция: Создание MTF таблиц версии 2

Создает основные таблицы для MTF модуля с поддержкой:
- Версионирования схем и алгоритмов
- Качества данных и мониторинга
- Отслеживания выполнения
- Операционных метрик
"""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mtf_v2_tables(engine):
    """Создание MTF таблиц версии 2"""

    # SQL для создания таблиц
    tables_sql = [
        """
        -- MTF Context таблица
        CREATE TABLE IF NOT EXISTS mtf_context (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            timestamp TIMESTAMP NOT NULL,

            -- Контекстные метрики
            score DOUBLE PRECISION NOT NULL,
            valid BOOLEAN NOT NULL DEFAULT TRUE,
            regime VARCHAR(20),

            -- Качество данных
            data_quality_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            data_age_minutes DOUBLE PRECISION,
            valid_rate DOUBLE PRECISION,
            nan_rate DOUBLE PRECISION,

            -- Версионирование
            schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
            algo_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            params_hash VARCHAR(16) NOT NULL,

            -- Метаданные
            features_json JSONB,
            warnings TEXT[],
            errors TEXT[],

            -- Временные метки
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """,
        """
        -- MTF Triggers таблица
        CREATE TABLE IF NOT EXISTS mtf_triggers (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            timeframe VARCHAR(10) NOT NULL,
            timestamp TIMESTAMP NOT NULL,

            -- Триггерные метрики
            p_up DOUBLE PRECISION NOT NULL,
            p_down DOUBLE PRECISION NOT NULL,
            accel INTEGER,
            micro_ok BOOLEAN,

            -- Качество данных
            data_quality_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            lookahead_guard BOOLEAN NOT NULL DEFAULT TRUE,
            future_data_detected BOOLEAN NOT NULL DEFAULT FALSE,

            -- Версионирование
            schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
            algo_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            params_hash VARCHAR(16) NOT NULL,

            -- Метаданные
            features_json JSONB,
            warnings TEXT[],
            errors TEXT[],

            -- Временные метки
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """,
        """
        -- MTF Consensus таблица
        CREATE TABLE IF NOT EXISTS mtf_consensus (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            horizon VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP NOT NULL,

            -- Консенсусные метрики
            side INTEGER NOT NULL,
            strength DOUBLE PRECISION NOT NULL,
            coverage DOUBLE PRECISION NOT NULL,
            disagreement_score DOUBLE PRECISION,

            -- Качество данных
            data_quality_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            consensus_confidence DOUBLE PRECISION,

            -- Версионирование
            schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
            algo_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
            params_hash VARCHAR(16) NOT NULL,

            -- Метаданные
            reasons TEXT[],
            timeframe_votes JSONB,
            warnings TEXT[],
            errors TEXT[],

            -- Временные метки
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """,
        """
        -- MTF Runs таблица
        CREATE TABLE IF NOT EXISTS mtf_runs (
            run_id VARCHAR(36) PRIMARY KEY,
            source VARCHAR(50) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'running',

            -- Метаданные выполнения
            env_hash VARCHAR(16) NOT NULL,
            params_hash VARCHAR(16) NOT NULL,
            start_time TIMESTAMP NOT NULL DEFAULT NOW(),
            end_time TIMESTAMP,

            -- Статистика выполнения
            records_processed INTEGER DEFAULT 0,
            records_written INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            warnings_count INTEGER DEFAULT 0,

            -- Метаданные
            config_json JSONB,
            errors_log TEXT[],
            warnings_log TEXT[],

            -- Временные метки
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """,
        """
        -- MTF Data Quality таблица
        CREATE TABLE IF NOT EXISTS mtf_data_quality (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            table_name VARCHAR(50) NOT NULL,
            timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

            -- Метрики качества
            freshness_minutes DOUBLE PRECISION,
            completeness_rate DOUBLE PRECISION,
            accuracy_rate DOUBLE PRECISION,
            consistency_score DOUBLE PRECISION,

            -- Детали качества
            missing_columns TEXT[],
            null_rates JSONB,
            anomaly_flags TEXT[],

            -- Статус
            overall_status VARCHAR(20) NOT NULL,
            alerts_triggered BOOLEAN DEFAULT FALSE,

            -- Временные метки
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """,
        """
        -- MTF Alerts таблица
        CREATE TABLE IF NOT EXISTS mtf_alerts (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36),
            alert_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

            -- Детали оповещения
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            context JSONB,

            -- Статус обработки
            acknowledged BOOLEAN DEFAULT FALSE,
            acknowledged_by VARCHAR(100),
            acknowledged_at TIMESTAMP,

            -- Каналы отправки
            channels_sent TEXT[],
            channels_failed TEXT[],

            -- Временные метки
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """,
        """
        -- MTF Signals таблица
        CREATE TABLE IF NOT EXISTS mtf_signals (
            id SERIAL PRIMARY KEY,
            run_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            horizon VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP NOT NULL,

            -- Сигнальные метрики
            side INTEGER NOT NULL,
            strength DOUBLE PRECISION NOT NULL,
            confidence DOUBLE PRECISION NOT NULL,
            expected_return DOUBLE PRECISION,

            -- Качество сигнала
            signal_quality VARCHAR(20) NOT NULL,
            lookahead_safe BOOLEAN NOT NULL DEFAULT TRUE,
            regime_appropriate BOOLEAN,

            -- Версионирование
            signal_version VARCHAR(10) NOT NULL DEFAULT 'v1',
            algo_version VARCHAR(20) NOT NULL,
            params_hash VARCHAR(16) NOT NULL,

            -- Метаданные
            reasoning TEXT[],
            supporting_data JSONB,
            warnings TEXT[],

            -- Временные метки
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        """,
    ]

    # Создание индексов
    indexes_sql = [
        # MTF Context индексы
        "CREATE INDEX IF NOT EXISTS idx_mtf_context_symbol_tf_ts ON mtf_context(symbol, timeframe, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_context_run_id ON mtf_context(run_id);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_context_quality ON mtf_context(data_quality_status);",
        # MTF Triggers индексы
        "CREATE INDEX IF NOT EXISTS idx_mtf_triggers_symbol_tf_ts ON mtf_triggers(symbol, timeframe, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_triggers_run_id ON mtf_triggers(run_id);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_triggers_quality ON mtf_triggers(data_quality_status);",
        # MTF Consensus индексы
        "CREATE INDEX IF NOT EXISTS idx_mtf_consensus_symbol_horizon_ts ON mtf_consensus(symbol, horizon, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_consensus_run_id ON mtf_consensus(run_id);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_consensus_side ON mtf_consensus(side);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_consensus_strength ON mtf_consensus(strength);",
        # MTF Runs индексы
        "CREATE INDEX IF NOT EXISTS idx_mtf_runs_source ON mtf_runs(source);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_runs_status ON mtf_runs(status);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_runs_start_time ON mtf_runs(start_time);",
        # MTF Data Quality индексы
        "CREATE INDEX IF NOT EXISTS idx_mtf_data_quality_run_id ON mtf_data_quality(run_id);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_data_quality_table ON mtf_data_quality(table_name);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_data_quality_status ON mtf_data_quality(overall_status);",
        # MTF Alerts индексы
        "CREATE INDEX IF NOT EXISTS idx_mtf_alerts_type ON mtf_alerts(alert_type);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_alerts_severity ON mtf_alerts(severity);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_alerts_timestamp ON mtf_alerts(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_alerts_acknowledged ON mtf_alerts(acknowledged);",
        # MTF Signals индексы
        "CREATE INDEX IF NOT EXISTS idx_mtf_signals_symbol_horizon_ts ON mtf_signals(symbol, horizon, timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_signals_run_id ON mtf_signals(run_id);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_signals_side ON mtf_signals(side);",
        "CREATE INDEX IF NOT EXISTS idx_mtf_signals_quality ON mtf_signals(signal_quality);",
    ]

    # Уникальные ограничения
    constraints_sql = [
        "ALTER TABLE mtf_context ADD CONSTRAINT IF NOT EXISTS uq_mtf_context_unique UNIQUE (symbol, timeframe, timestamp, run_id);",
        "ALTER TABLE mtf_triggers ADD CONSTRAINT IF NOT EXISTS uq_mtf_triggers_unique UNIQUE (symbol, timeframe, timestamp, run_id);",
        "ALTER TABLE mtf_consensus ADD CONSTRAINT IF NOT EXISTS uq_mtf_consensus_unique UNIQUE (symbol, horizon, timestamp, run_id);",
    ]

    try:
        with engine.connect() as conn:
            # Создание таблиц
            logger.info("Создание MTF таблиц версии 2...")
            for sql in tables_sql:
                conn.execute(text(sql))
                conn.commit()

            # Создание индексов
            logger.info("Создание индексов...")
            for sql in indexes_sql:
                conn.execute(text(sql))
                conn.commit()

            # Создание ограничений
            logger.info("Создание уникальных ограничений...")
            for sql in constraints_sql:
                conn.execute(text(sql))
                conn.commit()

            logger.info("✅ MTF таблицы версии 2 успешно созданы")

    except SQLAlchemyError as e:
        logger.error(f"❌ Ошибка при создании MTF таблиц: {e}")
        raise


def main():
    """Основная функция миграции"""
    from database import get_database_url

    try:
        # Получение URL базы данных
        database_url = get_database_url()
        engine = create_engine(database_url)

        # Создание таблиц
        create_mtf_v2_tables(engine)

        logger.info("🎉 Миграция MTF таблиц версии 2 завершена успешно")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка миграции: {e}")
        raise


if __name__ == "__main__":
    main()
