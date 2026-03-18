-- Migration 006: NOT NULL для метаданных версионирования
-- Политика: algo_version/run_id/params_hash всегда должны быть заполнены
-- Применение: psql -f 006_metadata_not_null.sql

BEGIN;

-- Заполняем NULL значения дефолтами перед добавлением NOT NULL
UPDATE core.market_data_ext
SET algo_version = 'unknown'
WHERE algo_version IS NULL;

UPDATE core.market_data_ext
SET run_id = 'legacy'
WHERE run_id IS NULL;

UPDATE core.market_data_ext
SET params_hash = 'legacy_no_hash'
WHERE params_hash IS NULL;

-- Добавляем NOT NULL constraints
ALTER TABLE core.market_data_ext
    ALTER COLUMN algo_version SET NOT NULL,
    ALTER COLUMN run_id SET NOT NULL,
    ALTER COLUMN params_hash SET NOT NULL;

COMMIT;
