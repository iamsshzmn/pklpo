-- Миграция 003: Расширение ops.sync_state
-- Дата: 2024-12-18
-- Описание: Добавление поля meta jsonb и индекса для pipeline+data_type

-- ============================================================================
-- 1. Добавляем поле meta jsonb
-- ============================================================================

ALTER TABLE ops.sync_state
ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN ops.sync_state.meta IS 'Дополнительные параметры: safety_lag_sec, lookback_sec, last_rowcount';

-- ============================================================================
-- 2. Добавляем CHECK constraint на data_type
-- ============================================================================

-- Удаляем старый constraint если есть
ALTER TABLE ops.sync_state
DROP CONSTRAINT IF EXISTS sync_state_data_type_check;

-- Добавляем новый
ALTER TABLE ops.sync_state
ADD CONSTRAINT sync_state_data_type_check
CHECK (data_type IN ('funding', 'oi', 'l2', 'ohlcv'));

-- ============================================================================
-- 3. Индекс для быстрого поиска по pipeline + data_type
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_sync_state_pipeline_type
ON ops.sync_state (pipeline, data_type);

-- ============================================================================
-- 4. Пример использования meta
-- ============================================================================

-- UPDATE ops.sync_state
-- SET meta = jsonb_build_object(
--     'safety_lag_sec', 120,
--     'lookback_sec', 600,
--     'last_rowcount', 1234
-- )
-- WHERE pipeline = 'okx_ext_raw_ingest';
