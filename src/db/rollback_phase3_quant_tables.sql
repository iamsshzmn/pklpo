-- Rollback: Phase 3 Quant Stack
-- Применять в порядке обратном миграции.

-- 3. Удаление таблицы ml_artifacts
DROP INDEX IF EXISTS idx_ml_artifacts_run_type;
DROP INDEX IF EXISTS idx_ml_artifacts_run;
DROP TABLE IF EXISTS ml_artifacts;

-- 2. Удаление таблицы labels
DROP INDEX IF EXISTS idx_labels_sym_tf_ts;
DROP INDEX IF EXISTS idx_labels_run_id;
DROP INDEX IF EXISTS idx_labels_sym_tf_ts_run;
DROP TABLE IF EXISTS labels;

-- 1. Удаление quant-колонок из ohlcv_p
DROP INDEX IF EXISTS idx_ohlcv_p_bars_mode;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS bars_mode;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS bars_source;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS turnover;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS volume_unit;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS ts_start;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS ts_end;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS duration_s;
ALTER TABLE ohlcv_p DROP COLUMN IF EXISTS trades_count;
