-- Market Selection: market_regime_history table
-- Stores global market regime history for STALE_REGIME fallback
-- and regime analysis

CREATE TABLE IF NOT EXISTS market_regime_history (
    -- Primary key
    ts_eval BIGINT PRIMARY KEY,  -- evaluation timestamp in milliseconds

    -- Regime classification
    global_regime TEXT NOT NULL,  -- TREND_UP, TREND_DOWN, RANGE, VOLATILE
    global_strength REAL NOT NULL,
    regime_confidence REAL NOT NULL,

    -- Per-TF regime breakdown
    regime_1d TEXT,
    regime_1d_strength REAL,
    regime_4h TEXT,
    regime_4h_strength REAL,
    regime_1h TEXT,
    regime_1h_strength REAL,

    -- Basket statistics (top-K symbols used)
    basket_size INTEGER,
    basket_symbols TEXT[],  -- symbols used for regime calculation

    -- Aggregated metrics from basket
    basket_adx_median REAL,
    basket_atr_close_median REAL,
    basket_ema_slope_median REAL,
    basket_volume_median REAL,

    -- Staleness tracking
    is_stale BOOLEAN DEFAULT false,
    stale_reason TEXT,
    last_valid_ts BIGINT,  -- if stale, when was last valid

    -- Metadata
    config_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_mrh_regime
    ON market_regime_history (global_regime);

CREATE INDEX IF NOT EXISTS idx_mrh_created
    ON market_regime_history (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mrh_not_stale
    ON market_regime_history (ts_eval)
    WHERE is_stale = false;

-- Comments
COMMENT ON TABLE market_regime_history IS 'Global market regime history for analysis and STALE_REGIME fallback';
COMMENT ON COLUMN market_regime_history.basket_symbols IS 'Top-K symbols by volume used for regime calculation';
COMMENT ON COLUMN market_regime_history.is_stale IS 'True if regime was copied from previous due to data lag';
