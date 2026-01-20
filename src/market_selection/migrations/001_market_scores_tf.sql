-- Market Selection: market_scores_tf table
-- Stores per-symbol, per-timeframe scoring history
-- Updated every 4 hours by market_selection DAG

CREATE TABLE IF NOT EXISTS market_scores_tf (
    -- Primary key
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts_eval BIGINT NOT NULL,  -- evaluation timestamp in milliseconds

    -- Raw metric values (before normalization)
    vol_raw REAL,             -- median(atr_14 / close)
    trend_q_raw REAL,         -- adx_norm * abs(ema_slope_norm)
    noise_raw REAL,           -- std(|returns|) / median(|returns|)
    stability_raw REAL,       -- dominance * (1 - switch_rate)
    liq_raw REAL,             -- median(volume) / (cv(volume) + 1)

    -- Normalized metric scores (0-1, percentile rank)
    vol_score REAL,
    trend_q_score REAL,
    noise_score REAL,
    stability_score REAL,
    liq_score REAL,

    -- Aggregated score for this TF
    score_tf_base REAL,       -- weighted sum of metric scores
    score_tf REAL,            -- score_tf_base * quality_score

    -- Quality gate results
    quality_score REAL,       -- combined quality metric (0-1)
    fill_rate REAL,           -- valid_bars / expected_bars
    gap_rate REAL,            -- gaps_count / expected_bars
    data_lag_seconds INTEGER, -- max(ohlcv_lag, feature_lag)
    valid_bars INTEGER,       -- bars with non-null key features
    expected_bars INTEGER,    -- expected bars in window
    eligible BOOLEAN NOT NULL DEFAULT false,

    -- Global regime at evaluation time
    global_regime TEXT,       -- TREND_UP, TREND_DOWN, RANGE, VOLATILE
    global_strength REAL,     -- 0-1
    regime_confidence REAL,   -- 0-1

    -- Metadata
    reason_flags TEXT[] DEFAULT '{}',  -- exclusion/warning reasons
    window_days INTEGER,               -- lookback window used
    config_hash TEXT NOT NULL,         -- for reproducibility
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (symbol, timeframe, ts_eval)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_mstf_tf_ts
    ON market_scores_tf (timeframe, ts_eval);

CREATE INDEX IF NOT EXISTS idx_mstf_symbol_tf
    ON market_scores_tf (symbol, timeframe);

CREATE INDEX IF NOT EXISTS idx_mstf_eligible_ts
    ON market_scores_tf (eligible, ts_eval)
    WHERE eligible = true;

CREATE INDEX IF NOT EXISTS idx_mstf_config_hash
    ON market_scores_tf (config_hash);

-- Comments
COMMENT ON TABLE market_scores_tf IS 'Per-symbol per-timeframe scoring history for market selection';
COMMENT ON COLUMN market_scores_tf.ts_eval IS 'Evaluation timestamp in milliseconds (UTC)';
COMMENT ON COLUMN market_scores_tf.score_tf IS 'Final TF score = score_tf_base * quality_score';
COMMENT ON COLUMN market_scores_tf.reason_flags IS 'Array of exclusion/warning flags like LOW_FILL, STALE_DATA, etc.';
COMMENT ON COLUMN market_scores_tf.config_hash IS 'SHA256 hash of config for reproducibility';
