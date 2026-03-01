-- Миграция 002: Разделение raw и normalized данных
-- Дата: 2024-12-18
-- Описание: Создание схем raw/core/ops и таблиц для хранения сырых и нормализованных данных

-- ============================================================================
-- 1. Создание схем
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS ops;

COMMENT ON SCHEMA raw IS 'Сырые данные от OKX без трансформаций';
COMMENT ON SCHEMA core IS 'Нормализованные и агрегированные данные';
COMMENT ON SCHEMA ops IS 'Операционные данные: watermarks, состояние синхронизации';

-- ============================================================================
-- 2. RAW таблица: сырые данные ext (funding, oi, l2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS raw.market_data_ext_raw (
    symbol        TEXT        NOT NULL,
    data_type     TEXT        NOT NULL CHECK (data_type IN ('funding', 'oi', 'l2')),
    ts            TIMESTAMPTZ NOT NULL,
    payload       JSONB       NOT NULL,
    payload_hash  TEXT        NOT NULL,
    source        TEXT        NOT NULL DEFAULT 'okx',
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (symbol, data_type, ts, payload_hash)
);

-- Индекс для быстрого поиска по типу и символу
CREATE INDEX IF NOT EXISTS ix_ext_raw_type_symbol_ts
    ON raw.market_data_ext_raw (data_type, symbol, ts DESC);

-- BRIN индекс для больших объёмов (эффективен для временных рядов)
CREATE INDEX IF NOT EXISTS ix_ext_raw_ts_brin
    ON raw.market_data_ext_raw USING BRIN (ts);

COMMENT ON TABLE raw.market_data_ext_raw IS 'Сырые данные OKX: funding rates, open interest, L2 order book';
COMMENT ON COLUMN raw.market_data_ext_raw.payload_hash IS 'SHA256 хеш payload для защиты от дублей';
COMMENT ON COLUMN raw.market_data_ext_raw.ts IS 'Исходный timestamp от OKX (UTC)';

-- ============================================================================
-- 3. CORE таблица: нормализованные и агрегированные данные
-- ============================================================================

CREATE TABLE IF NOT EXISTS core.market_data_ext (
    symbol        TEXT        NOT NULL,
    timeframe     TEXT        NOT NULL,  -- '1m', '5m', '15m', '1H'
    bar_timestamp TIMESTAMPTZ NOT NULL,  -- строго из swap.swap_ohlcv_p

    -- Funding Rate
    funding_rate  NUMERIC     NULL,
    funding_ts    TIMESTAMPTZ NULL,

    -- Open Interest
    open_interest NUMERIC     NULL,
    oi_ts         TIMESTAMPTZ NULL,

    -- L2 Order Book метрики
    spread_bps    NUMERIC     NULL,
    imbalance     NUMERIC     NULL,
    l2_ts         TIMESTAMPTZ NULL,

    -- Версионирование и трассировка
    algo_version  TEXT        NOT NULL,
    run_id        TEXT        NOT NULL,
    params_hash   TEXT        NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (symbol, timeframe, bar_timestamp)
);

-- Индексы для быстрого доступа
CREATE INDEX IF NOT EXISTS ix_ext_core_tf_ts
    ON core.market_data_ext (timeframe, bar_timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_ext_core_symbol_tf_ts
    ON core.market_data_ext (symbol, timeframe, bar_timestamp DESC);

COMMENT ON TABLE core.market_data_ext IS 'Нормализованные ext данные, привязанные к барам OHLCV';
COMMENT ON COLUMN core.market_data_ext.bar_timestamp IS 'Timestamp бара из swap.swap_ohlcv_p (источник истины)';
COMMENT ON COLUMN core.market_data_ext.params_hash IS 'SHA256 хеш параметров нормализации для воспроизводимости';

-- ============================================================================
-- 4. OPS таблица: watermark для инкрементальной загрузки
-- ============================================================================

CREATE TABLE IF NOT EXISTS ops.sync_state (
    pipeline    TEXT        NOT NULL,
    symbol      TEXT        NOT NULL,
    data_type   TEXT        NOT NULL,
    last_ts     TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (pipeline, symbol, data_type)
);

-- Триггер для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION ops.update_sync_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_state_updated_at ON ops.sync_state;
CREATE TRIGGER trg_sync_state_updated_at
    BEFORE UPDATE ON ops.sync_state
    FOR EACH ROW EXECUTE FUNCTION ops.update_sync_state_updated_at();

COMMENT ON TABLE ops.sync_state IS 'Watermark для инкрементальной загрузки данных';
COMMENT ON COLUMN ops.sync_state.pipeline IS 'Имя pipeline: raw_ingest, normalize_1m, aggregate';
COMMENT ON COLUMN ops.sync_state.last_ts IS 'Последний обработанный timestamp';

-- ============================================================================
-- 5. Retention: партиционирование по месяцам (опционально, для будущего)
-- ============================================================================

-- Примечание: для больших объёмов L2 рекомендуется партиционирование.
-- Пока используем обычные таблицы с retention через DELETE.

-- ============================================================================
-- 6. Гранты (если нужны отдельные роли)
-- ============================================================================

-- GRANT USAGE ON SCHEMA raw TO pklpo_app;
-- GRANT USAGE ON SCHEMA core TO pklpo_app;
-- GRANT USAGE ON SCHEMA ops TO pklpo_app;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA raw TO pklpo_app;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA core TO pklpo_app;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA ops TO pklpo_app;
