-- Миграция 001: Создание таблиц market_meta
-- Дата: 2024-01-XX
-- Описание: Создание схемы для хранения метаданных рынка, валидации и кэша

-- Создание таблицы метаданных рынка
CREATE TABLE IF NOT EXISTS market_meta (
    id SERIAL PRIMARY KEY,
    symbol_id VARCHAR(50) NOT NULL,
    inst_id VARCHAR(50) NOT NULL,
    inst_type VARCHAR(20) NOT NULL, -- SPOT, SWAP, FUTURES, OPTIONS
    base_ccy VARCHAR(10) NOT NULL,
    quote_ccy VARCHAR(10) NOT NULL,
    settle_ccy VARCHAR(10),

    -- Размеры тика и лота
    tick_size_step DOUBLE PRECISION,
    tick_size_min DOUBLE PRECISION,
    tick_size_max DOUBLE PRECISION,

    lot_size_step DOUBLE PRECISION,
    lot_size_min DOUBLE PRECISION,
    lot_size_max DOUBLE PRECISION,

    -- Номинальная стоимость и комиссии
    contract_val DOUBLE PRECISION,
    fee_maker DOUBLE PRECISION, -- Комиссия мейкера (в %)
    fee_taker DOUBLE PRECISION, -- Комиссия тейкера (в %)

    -- Плечо и маржа
    max_leverage DOUBLE PRECISION,
    margin_mode VARCHAR(20), -- ISOLATED, CROSS
    position_mode VARCHAR(20), -- LONG_SHORT, NET
    maint_margin_rate DOUBLE PRECISION,

    -- Ставка финансирования
    funding_rate DOUBLE PRECISION,
    next_funding_time TIMESTAMP,
    funding_interval_hours INTEGER,

    -- Параметры ликвидности
    min_volume_24h DOUBLE PRECISION,
    min_trades_24h INTEGER,
    spread_threshold DOUBLE PRECISION, -- Максимальный спред в %

    -- Статус и временные метки
    state VARCHAR(20) NOT NULL DEFAULT 'live', -- live, suspended, expired
    is_tradable BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы кэша валидации
CREATE TABLE IF NOT EXISTS validation_cache (
    id SERIAL PRIMARY KEY,
    symbol_id VARCHAR(50) NOT NULL,
    validation_type VARCHAR(50) NOT NULL, -- order, risk, liquidity
    params_hash VARCHAR(64) NOT NULL, -- Хеш параметров валидации
    result TEXT NOT NULL, -- JSON результат валидации
    is_valid BOOLEAN NOT NULL,
    violations TEXT, -- JSON список нарушений
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL -- TTL для кэша
);

-- Создание таблицы лимитов риска
CREATE TABLE IF NOT EXISTS risk_limits (
    id SERIAL PRIMARY KEY,
    symbol_id VARCHAR(50) NOT NULL,
    risk_level VARCHAR(20) NOT NULL, -- LOW, MEDIUM, HIGH

    -- Лимиты позиций
    max_position_size DOUBLE PRECISION,
    max_notional_value DOUBLE PRECISION,
    max_position_size_pct DOUBLE PRECISION, -- % от баланса

    -- Лимиты экспозиции
    max_total_exposure_pct DOUBLE PRECISION,
    max_daily_loss_pct DOUBLE PRECISION,
    max_weekly_loss_pct DOUBLE PRECISION,

    -- Лимиты корреляции
    max_correlation DOUBLE PRECISION,
    cooldown_hours INTEGER,

    -- Временные метки
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы лога валидаций
CREATE TABLE IF NOT EXISTS validation_log (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) NOT NULL,
    symbol_id VARCHAR(50) NOT NULL,
    validation_type VARCHAR(50) NOT NULL,

    -- Параметры валидации
    price DOUBLE PRECISION,
    qty DOUBLE PRECISION,
    leverage DOUBLE PRECISION,
    margin_mode VARCHAR(20),

    -- Результат
    is_valid BOOLEAN NOT NULL,
    violations TEXT, -- JSON список нарушений
    processing_time_ms INTEGER,

    -- Метаданные
    algo_version VARCHAR(50),
    params_hash VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для market_meta
CREATE INDEX IF NOT EXISTS idx_market_meta_symbol_id ON market_meta(symbol_id);
CREATE INDEX IF NOT EXISTS idx_market_meta_inst_type ON market_meta(inst_type);
CREATE INDEX IF NOT EXISTS idx_market_meta_tradable ON market_meta(is_tradable);
CREATE INDEX IF NOT EXISTS idx_market_meta_updated ON market_meta(updated_at);

-- Создание индексов для validation_cache
CREATE INDEX IF NOT EXISTS idx_validation_cache_symbol_type ON validation_cache(symbol_id, validation_type);
CREATE INDEX IF NOT EXISTS idx_validation_cache_expires ON validation_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_validation_cache_params ON validation_cache(params_hash);

-- Создание индексов для risk_limits
CREATE INDEX IF NOT EXISTS idx_risk_limits_symbol_risk ON risk_limits(symbol_id, risk_level);

-- Создание индексов для validation_log
CREATE INDEX IF NOT EXISTS idx_validation_log_run_id ON validation_log(run_id);
CREATE INDEX IF NOT EXISTS idx_validation_log_symbol_time ON validation_log(symbol_id, created_at);
CREATE INDEX IF NOT EXISTS idx_validation_log_type_time ON validation_log(validation_type, created_at);

-- Создание уникальных ограничений
ALTER TABLE market_meta ADD CONSTRAINT IF NOT EXISTS uq_market_meta_symbol_id UNIQUE (symbol_id);
ALTER TABLE risk_limits ADD CONSTRAINT IF NOT EXISTS uq_risk_limits_symbol_risk UNIQUE (symbol_id, risk_level);

-- Создание триггера для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_market_meta_updated_at
    BEFORE UPDATE ON market_meta
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_risk_limits_updated_at
    BEFORE UPDATE ON risk_limits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Вставка базовых лимитов риска
INSERT INTO risk_limits (symbol_id, risk_level, max_position_size_pct, max_total_exposure_pct, max_daily_loss_pct, max_weekly_loss_pct) VALUES
('*', 'LOW', 0.05, 0.25, 0.02, 0.08),
('*', 'MEDIUM', 0.1, 0.5, 0.05, 0.15),
('*', 'HIGH', 0.2, 0.75, 0.1, 0.25)
ON CONFLICT (symbol_id, risk_level) DO NOTHING;

-- Комментарии к таблицам
COMMENT ON TABLE market_meta IS 'Метаданные инструментов рынка';
COMMENT ON TABLE validation_cache IS 'Кэш результатов валидации';
COMMENT ON TABLE risk_limits IS 'Лимиты риска по инструментам';
COMMENT ON TABLE validation_log IS 'Лог валидаций для аудита';
