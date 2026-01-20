-- Market Selection: market_universe table
-- Stores final selected trading pairs per version
-- Each version is a snapshot of the trading universe

CREATE TABLE IF NOT EXISTS market_universe (
    -- Primary key
    ts_version BIGINT NOT NULL,  -- version timestamp in milliseconds
    symbol TEXT NOT NULL,

    -- Scores
    final_score REAL NOT NULL,   -- MTF-aggregated score
    rank INTEGER NOT NULL,       -- position in top-N

    -- Per-TF scores (for debugging)
    score_4h REAL,
    score_1h REAL,
    score_15m REAL,
    score_5m REAL,
    best_tf TEXT,                -- TF with highest score
    worst_tf TEXT,               -- TF with lowest score

    -- Stability metrics (for hysteresis)
    score_std_7d REAL,           -- score volatility over 7 days
    score_std_30d REAL,          -- score volatility over 30 days
    days_in_universe INTEGER,    -- consecutive days in universe

    -- Regime at selection time
    global_regime_at_time TEXT,
    global_strength_at_time REAL,

    -- Flags and penalties applied
    reason_flags TEXT[] DEFAULT '{}',
    penalty_applied REAL DEFAULT 0,  -- total penalty (missing TF, etc.)

    -- Versioning
    config_hash TEXT NOT NULL,
    source_version BIGINT,       -- if fallback, points to original version

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (ts_version, symbol)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_mu_ts_version
    ON market_universe (ts_version);

CREATE INDEX IF NOT EXISTS idx_mu_symbol
    ON market_universe (symbol);

CREATE INDEX IF NOT EXISTS idx_mu_rank
    ON market_universe (ts_version, rank);

CREATE INDEX IF NOT EXISTS idx_mu_final_score
    ON market_universe (ts_version, final_score DESC);

-- Comments
COMMENT ON TABLE market_universe IS 'Selected trading pairs per version (updated every 4 hours)';
COMMENT ON COLUMN market_universe.ts_version IS 'Universe version timestamp in milliseconds';
COMMENT ON COLUMN market_universe.rank IS 'Position in top-N selection (1 = best)';
COMMENT ON COLUMN market_universe.source_version IS 'If fallback used, points to the good version copied from';
