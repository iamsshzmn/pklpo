-- Migration: Add versioning fields to indicators table
-- Task: FEAT-001 - Версионность данных для ML
-- Date: 2025-10-27
-- Author: Features Module Team

-- Add version fields to indicators table
ALTER TABLE indicators
  ADD COLUMN IF NOT EXISTS algorithm_version VARCHAR(20) DEFAULT '1.0.0',
  ADD COLUMN IF NOT EXISTS snapshot_id VARCHAR(50),
  ADD COLUMN IF NOT EXISTS calculation_config JSONB;

-- Add indexes for versioning queries
CREATE INDEX IF NOT EXISTS idx_indicators_version
  ON indicators(algorithm_version);

CREATE INDEX IF NOT EXISTS idx_indicators_snapshot
  ON indicators(snapshot_id);

-- Create calculation metadata table
CREATE TABLE IF NOT EXISTS calculation_metadata (
  snapshot_id VARCHAR(50) PRIMARY KEY,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMP,
  algorithm_version VARCHAR(20) NOT NULL,
  module_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
  config JSONB NOT NULL,
  symbols TEXT[],
  timeframes TEXT[],
  status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'failed', 'cancelled')),
  rows_calculated INTEGER DEFAULT 0,
  error_message TEXT,
  execution_duration_seconds NUMERIC(10, 2)
);

-- Indexes for metadata queries
CREATE INDEX IF NOT EXISTS idx_calc_metadata_created
  ON calculation_metadata(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_calc_metadata_status
  ON calculation_metadata(status);

CREATE INDEX IF NOT EXISTS idx_calc_metadata_version
  ON calculation_metadata(algorithm_version);

-- Create view for reproducibility queries
CREATE OR REPLACE VIEW v_calculation_summary AS
SELECT
  cm.snapshot_id,
  cm.created_at,
  cm.completed_at,
  cm.algorithm_version,
  cm.module_version,
  cm.status,
  cm.rows_calculated,
  cm.symbols,
  cm.timeframes,
  COUNT(DISTINCT i.symbol) as symbols_count,
  COUNT(DISTINCT i.timeframe) as timeframes_count,
  COUNT(*) as total_rows,
  cm.execution_duration_seconds
FROM calculation_metadata cm
LEFT JOIN indicators i ON i.snapshot_id = cm.snapshot_id
GROUP BY
  cm.snapshot_id, cm.created_at, cm.completed_at,
  cm.algorithm_version, cm.module_version, cm.status,
  cm.rows_calculated, cm.symbols, cm.timeframes,
  cm.execution_duration_seconds
ORDER BY cm.created_at DESC;

-- Grant permissions (adjust for your user)
GRANT SELECT, INSERT, UPDATE ON calculation_metadata TO pklpo_user;
GRANT SELECT ON v_calculation_summary TO pklpo_user;

-- Add comment
COMMENT ON TABLE calculation_metadata IS
  'Metadata for feature calculations to enable ML model reproducibility';

COMMENT ON COLUMN indicators.algorithm_version IS
  'Version of the indicator calculation algorithm';

COMMENT ON COLUMN indicators.snapshot_id IS
  'Reference to calculation_metadata.snapshot_id for grouping calculations';

COMMENT ON COLUMN indicators.calculation_config IS
  'JSON configuration used for this specific calculation';

-- Rollback script (if needed)
-- ALTER TABLE indicators DROP COLUMN IF EXISTS algorithm_version;
-- ALTER TABLE indicators DROP COLUMN IF EXISTS snapshot_id;
-- ALTER TABLE indicators DROP COLUMN IF EXISTS calculation_config;
-- DROP VIEW IF EXISTS v_calculation_summary;
-- DROP TABLE IF EXISTS calculation_metadata;
