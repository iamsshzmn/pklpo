-- Market Selection: market_universe_versions table
-- Atomic versioning of universe snapshots
-- Enables fallback and audit trail

CREATE TABLE IF NOT EXISTS market_universe_versions (
    -- Primary key
    ts_version BIGINT PRIMARY KEY,  -- version timestamp in milliseconds

    -- Evaluation context
    ts_eval BIGINT NOT NULL,        -- data boundary used for evaluation

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'building',
    -- Possible values: building, published, failed, fallback_prev

    -- Universe statistics
    universe_size INTEGER,          -- number of symbols in this version
    eligible_count INTEGER,         -- total eligible symbols before top-N

    -- Per-TF statistics
    eligible_5m INTEGER,
    eligible_15m INTEGER,
    eligible_1h INTEGER,
    eligible_4h INTEGER,

    -- Regime at evaluation
    global_regime TEXT,
    global_strength REAL,

    -- Quality metrics
    avg_quality_score REAL,         -- average quality across universe
    min_final_score REAL,           -- lowest score in universe
    max_final_score REAL,           -- highest score in universe

    -- Fallback tracking
    source_version BIGINT,          -- if fallback, original version
    fallback_reason TEXT,           -- why fallback was triggered

    -- Execution metadata
    config_hash TEXT NOT NULL,
    execution_time_seconds REAL,    -- how long the run took
    notes TEXT,                     -- additional info

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Foreign key to source version (self-referential)
    CONSTRAINT fk_source_version
        FOREIGN KEY (source_version)
        REFERENCES market_universe_versions(ts_version)
        ON DELETE SET NULL
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_muv_status
    ON market_universe_versions (status);

CREATE INDEX IF NOT EXISTS idx_muv_created
    ON market_universe_versions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_muv_published
    ON market_universe_versions (ts_version)
    WHERE status = 'published';

-- Comments
COMMENT ON TABLE market_universe_versions IS 'Atomic versioning of universe snapshots with status tracking';
COMMENT ON COLUMN market_universe_versions.status IS 'building=in progress, published=success, failed=error, fallback_prev=used previous';
COMMENT ON COLUMN market_universe_versions.source_version IS 'For fallback: points to the version data was copied from';
