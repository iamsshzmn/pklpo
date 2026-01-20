-- MTF System Database Schemas
-- Схемы таблиц для MTF модулей

-- Таблица для хранения результатов Context модуля
CREATE TABLE IF NOT EXISTS mtf_context (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Результаты анализа режима рынка
    dominant_regime VARCHAR(20) NOT NULL, -- 'trend_up', 'trend_down', 'flat'
    regime_confidence DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000

    -- Общий score
    overall_score DECIMAL(8,6) NOT NULL, -- -1.000000 - 1.000000

    -- Детальные результаты по таймфреймам
    timeframe_results JSONB NOT NULL,

    -- Метаданные
    valid BOOLEAN NOT NULL DEFAULT TRUE,
    errors TEXT[],
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Индексы
    UNIQUE(symbol, timeframe, timestamp)
);

-- Индексы для mtf_context
CREATE INDEX IF NOT EXISTS idx_mtf_context_symbol_timeframe ON mtf_context(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_mtf_context_timestamp ON mtf_context(timestamp);
CREATE INDEX IF NOT EXISTS idx_mtf_context_regime ON mtf_context(dominant_regime);
CREATE INDEX IF NOT EXISTS idx_mtf_context_created_at ON mtf_context(created_at);

-- Таблица для хранения результатов Triggers модуля
CREATE TABLE IF NOT EXISTS mtf_triggers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Основные вероятности
    overall_p_up DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000
    overall_p_down DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000

    -- Ускорение
    acceleration_type VARCHAR(20) NOT NULL, -- 'bullish', 'bearish', 'neutral'
    acceleration_strength DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000

    -- Микро-фильтры
    micro_ok BOOLEAN NOT NULL DEFAULT FALSE,
    micro_filter_score DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000

    -- Детальные результаты по таймфреймам
    timeframe_results JSONB NOT NULL,

    -- Метаданные
    valid BOOLEAN NOT NULL DEFAULT TRUE,
    errors TEXT[],
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Индексы
    UNIQUE(symbol, timeframe, timestamp)
);

-- Индексы для mtf_triggers
CREATE INDEX IF NOT EXISTS idx_mtf_triggers_symbol_timeframe ON mtf_triggers(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_mtf_triggers_timestamp ON mtf_triggers(timestamp);
CREATE INDEX IF NOT EXISTS idx_mtf_triggers_acceleration ON mtf_triggers(acceleration_type);
CREATE INDEX IF NOT EXISTS idx_mtf_triggers_micro_ok ON mtf_triggers(micro_ok);
CREATE INDEX IF NOT EXISTS idx_mtf_triggers_created_at ON mtf_triggers(created_at);

-- Таблица для хранения результатов Consensus модуля
CREATE TABLE IF NOT EXISTS mtf_consensus (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframes TEXT[] NOT NULL, -- Массив таймфреймов
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Основные результаты консенсуса
    consensus_type VARCHAR(20) NOT NULL, -- 'strong_bullish', 'bullish', 'neutral', 'bearish', 'strong_bearish', 'conflicted'
    confidence_level VARCHAR(20) NOT NULL, -- 'very_high', 'high', 'medium', 'low', 'very_low'
    consensus_score DECIMAL(8,6) NOT NULL, -- -1.000000 - 1.000000

    -- Веса и метрики
    context_weight DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000
    triggers_weight DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000
    coverage_ratio DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000
    disagreement_ratio DECIMAL(5,4) NOT NULL, -- 0.0000 - 1.0000

    -- Veto логика
    veto_applied BOOLEAN NOT NULL DEFAULT FALSE,
    veto_reasons TEXT[],

    -- Детальные результаты
    timeframe_consensus JSONB NOT NULL,
    evidence_summary JSONB NOT NULL,

    -- Метаданные
    valid BOOLEAN NOT NULL DEFAULT TRUE,
    errors TEXT[],
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Индексы
    UNIQUE(symbol, timeframes, timestamp)
);

-- Индексы для mtf_consensus
CREATE INDEX IF NOT EXISTS idx_mtf_consensus_symbol ON mtf_consensus(symbol);
CREATE INDEX IF NOT EXISTS idx_mtf_consensus_timestamp ON mtf_consensus(timestamp);
CREATE INDEX IF NOT EXISTS idx_mtf_consensus_type ON mtf_consensus(consensus_type);
CREATE INDEX IF NOT EXISTS idx_mtf_consensus_confidence ON mtf_consensus(confidence_level);
CREATE INDEX IF NOT EXISTS idx_mtf_consensus_veto ON mtf_consensus(veto_applied);
CREATE INDEX IF NOT EXISTS idx_mtf_consensus_created_at ON mtf_consensus(created_at);

-- Таблица для хранения результатов Pipeline модуля
CREATE TABLE IF NOT EXISTS mtf_pipeline (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframes TEXT[] NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Статус обработки
    status VARCHAR(20) NOT NULL, -- 'success', 'partial', 'failed'
    processing_stage VARCHAR(20) NOT NULL, -- 'context', 'triggers', 'consensus', 'integration', 'completed'

    -- Ссылки на результаты модулей
    context_id INTEGER REFERENCES mtf_context(id),
    triggers_id INTEGER REFERENCES mtf_triggers(id),
    consensus_id INTEGER REFERENCES mtf_consensus(id),

    -- Метаданные
    total_processing_time_ms INTEGER NOT NULL,
    errors TEXT[],
    warnings TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Индексы
    UNIQUE(symbol, timeframes, timestamp)
);

-- Индексы для mtf_pipeline
CREATE INDEX IF NOT EXISTS idx_mtf_pipeline_symbol ON mtf_pipeline(symbol);
CREATE INDEX IF NOT EXISTS idx_mtf_pipeline_timestamp ON mtf_pipeline(timestamp);
CREATE INDEX IF NOT EXISTS idx_mtf_pipeline_status ON mtf_pipeline(status);
CREATE INDEX IF NOT EXISTS idx_mtf_pipeline_stage ON mtf_pipeline(processing_stage);
CREATE INDEX IF NOT EXISTS idx_mtf_pipeline_created_at ON mtf_pipeline(created_at);

-- Таблица для хранения результатов Integration модуля
CREATE TABLE IF NOT EXISTS mtf_integration (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframes TEXT[] NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Статус интеграции
    status VARCHAR(20) NOT NULL, -- 'success', 'partial', 'failed'

    -- Результаты интеграции с внешними системами
    okx_success BOOLEAN DEFAULT FALSE,
    database_success BOOLEAN DEFAULT FALSE,
    notifications_sent BOOLEAN DEFAULT FALSE,

    -- Метаданные
    processing_time_ms INTEGER,
    errors TEXT[],
    warnings TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Индексы
    UNIQUE(symbol, timeframes, timestamp)
);

-- Индексы для mtf_integration
CREATE INDEX IF NOT EXISTS idx_mtf_integration_symbol ON mtf_integration(symbol);
CREATE INDEX IF NOT EXISTS idx_mtf_integration_timestamp ON mtf_integration(timestamp);
CREATE INDEX IF NOT EXISTS idx_mtf_integration_status ON mtf_integration(status);
CREATE INDEX IF NOT EXISTS idx_mtf_integration_created_at ON mtf_integration(created_at);

-- Представления для удобного доступа к данным

-- Представление для получения последних результатов MTF по символу
CREATE OR REPLACE VIEW mtf_latest_results AS
SELECT
    p.symbol,
    p.timeframes,
    p.timestamp,
    p.status as pipeline_status,
    p.processing_stage,

    -- Context результаты
    c.dominant_regime,
    c.regime_confidence,
    c.overall_score as context_score,

    -- Triggers результаты
    t.overall_p_up,
    t.overall_p_down,
    t.acceleration_type,
    t.micro_ok,

    -- Consensus результаты
    cons.consensus_type,
    cons.confidence_level,
    cons.consensus_score,
    cons.veto_applied,

    -- Integration результаты
    i.status as integration_status,

    p.total_processing_time_ms,
    p.created_at
FROM mtf_pipeline p
LEFT JOIN mtf_context c ON p.context_id = c.id
LEFT JOIN mtf_triggers t ON p.triggers_id = t.id
LEFT JOIN mtf_consensus cons ON p.consensus_id = cons.id
LEFT JOIN mtf_integration i ON p.symbol = i.symbol AND p.timeframes = i.timeframes AND p.timestamp = i.timestamp
WHERE p.timestamp = (
    SELECT MAX(timestamp)
    FROM mtf_pipeline p2
    WHERE p2.symbol = p.symbol
);

-- Представление для статистики MTF системы
CREATE OR REPLACE VIEW mtf_statistics AS
SELECT
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(*) as total_processed,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
    AVG(total_processing_time_ms) as avg_processing_time_ms,
    COUNT(CASE WHEN consensus_type = 'strong_bullish' THEN 1 END) as strong_bullish_signals,
    COUNT(CASE WHEN consensus_type = 'strong_bearish' THEN 1 END) as strong_bearish_signals,
    COUNT(CASE WHEN consensus_type = 'conflicted' THEN 1 END) as conflicted_signals
FROM mtf_pipeline p
LEFT JOIN mtf_consensus c ON p.consensus_id = c.id
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC;

-- Комментарии к таблицам
COMMENT ON TABLE mtf_context IS 'Результаты анализа режимов рынка (Context модуль)';
COMMENT ON TABLE mtf_triggers IS 'Результаты генерации триггеров разворота (Triggers модуль)';
COMMENT ON TABLE mtf_consensus IS 'Результаты агрегации сигналов (Consensus модуль)';
COMMENT ON TABLE mtf_pipeline IS 'Результаты оркестрации обработки (Pipeline модуль)';
COMMENT ON TABLE mtf_integration IS 'Результаты интеграции с внешними системами (Integration модуль)';

COMMENT ON VIEW mtf_latest_results IS 'Последние результаты MTF анализа по символам';
COMMENT ON VIEW mtf_statistics IS 'Статистика работы MTF системы по часам';
