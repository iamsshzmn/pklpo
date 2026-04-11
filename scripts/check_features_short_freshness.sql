-- Freshness check for features_calc_short.
--
-- What it checks:
-- 1. Latest OHLCV timestamp in swap_ohlcv_p for each short timeframe
-- 2. Latest feature timestamp in indicators_p for the same timeframe
-- 3. OHLCV lag versus expected closed bar
-- 4. Feature lag versus latest OHLCV
-- 5. Whether numeric short indicators are actually present on the latest feature bar
--
-- Intended usage:
-- - psql
-- - Metabase SQL editor
-- - ad-hoc operational checks after DAG reruns

WITH timeframe_cfg AS (
    SELECT *
    FROM (
        VALUES
            ('1m'::text,   60::bigint,    240::bigint,   300::bigint),
            ('5m'::text,  300::bigint,    240::bigint,   300::bigint),
            ('15m'::text, 900::bigint,   1200::bigint,   900::bigint),
            ('30m'::text, 1800::bigint,  1200::bigint,  1800::bigint),
            ('1H'::text,  3600::bigint,  1200::bigint,  3600::bigint),
            ('4H'::text,  14400::bigint, 1200::bigint, 14400::bigint),
            ('1D'::text,  86400::bigint, 1200::bigint, 86400::bigint)
    ) AS t(timeframe, tf_seconds, max_ohlcv_lag_seconds, max_feature_lag_seconds)
),
clock AS (
    SELECT
        (EXTRACT(EPOCH FROM NOW() AT TIME ZONE 'UTC'))::bigint AS now_utc_seconds
),
expected_bar AS (
    SELECT
        cfg.timeframe,
        cfg.tf_seconds,
        cfg.max_ohlcv_lag_seconds,
        cfg.max_feature_lag_seconds,
        ((clock.now_utc_seconds / cfg.tf_seconds) * cfg.tf_seconds - cfg.tf_seconds) * 1000
            AS expected_closed_bar_ts_ms
    FROM timeframe_cfg cfg
    CROSS JOIN clock
),
ohlcv_latest AS (
    SELECT
        timeframe,
        MAX(timestamp) AS ohlcv_max_ts_ms
    FROM swap_ohlcv_p
    WHERE timeframe IN (SELECT timeframe FROM timeframe_cfg)
    GROUP BY timeframe
),
feature_latest AS (
    SELECT
        timeframe,
        MAX(timestamp) AS feature_max_ts_ms
    FROM indicators_p
    WHERE timeframe IN (SELECT timeframe FROM timeframe_cfg)
    GROUP BY timeframe
),
latest_feature_rows AS (
    SELECT
        i.timeframe,
        COUNT(*) AS latest_rows_total,
        COUNT(*) FILTER (WHERE i.data_status = 'ok') AS latest_rows_ok,
        COUNT(*) FILTER (WHERE i.failed_groups IS NOT NULL AND btrim(i.failed_groups) <> '') AS latest_rows_failed_groups,
        COUNT(*) FILTER (WHERE i.rsi_14 IS NOT NULL) AS latest_rows_with_rsi_14,
        COUNT(*) FILTER (WHERE i.macd IS NOT NULL) AS latest_rows_with_macd,
        COUNT(*) FILTER (WHERE i.macd_signal IS NOT NULL) AS latest_rows_with_macd_signal,
        COUNT(*) FILTER (WHERE i.macd_histogram IS NOT NULL) AS latest_rows_with_macd_histogram
    FROM indicators_p i
    JOIN feature_latest f
      ON f.timeframe = i.timeframe
     AND f.feature_max_ts_ms = i.timestamp
    GROUP BY i.timeframe
)
SELECT
    e.timeframe,
    to_timestamp(e.expected_closed_bar_ts_ms / 1000.0) AT TIME ZONE 'UTC' AS expected_closed_bar_utc,
    o.ohlcv_max_ts_ms,
    to_timestamp(o.ohlcv_max_ts_ms / 1000.0) AT TIME ZONE 'UTC' AS ohlcv_max_utc,
    f.feature_max_ts_ms,
    to_timestamp(f.feature_max_ts_ms / 1000.0) AT TIME ZONE 'UTC' AS feature_max_utc,
    ROUND((e.expected_closed_bar_ts_ms - o.ohlcv_max_ts_ms) / 1000.0, 2) AS ohlcv_lag_seconds,
    ROUND((o.ohlcv_max_ts_ms - f.feature_max_ts_ms) / 1000.0, 2) AS feature_lag_seconds,
    e.max_ohlcv_lag_seconds,
    e.max_feature_lag_seconds,
    COALESCE(l.latest_rows_total, 0) AS latest_rows_total,
    COALESCE(l.latest_rows_ok, 0) AS latest_rows_ok,
    COALESCE(l.latest_rows_failed_groups, 0) AS latest_rows_failed_groups,
    COALESCE(l.latest_rows_with_rsi_14, 0) AS latest_rows_with_rsi_14,
    COALESCE(l.latest_rows_with_macd, 0) AS latest_rows_with_macd,
    COALESCE(l.latest_rows_with_macd_signal, 0) AS latest_rows_with_macd_signal,
    COALESCE(l.latest_rows_with_macd_histogram, 0) AS latest_rows_with_macd_histogram,
    CASE
        WHEN o.ohlcv_max_ts_ms IS NULL THEN 'NO_OHLCV'
        WHEN f.feature_max_ts_ms IS NULL THEN 'NO_FEATURES'
        WHEN (e.expected_closed_bar_ts_ms - o.ohlcv_max_ts_ms) / 1000.0 >= e.max_ohlcv_lag_seconds THEN 'STALE_OHLCV'
        WHEN (o.ohlcv_max_ts_ms - f.feature_max_ts_ms) / 1000.0 > e.max_feature_lag_seconds THEN 'STALE_FEATURES'
        WHEN COALESCE(l.latest_rows_total, 0) = 0 THEN 'NO_LATEST_ROWS'
        WHEN COALESCE(l.latest_rows_with_rsi_14, 0) = 0
          OR COALESCE(l.latest_rows_with_macd, 0) = 0
          OR COALESCE(l.latest_rows_with_macd_signal, 0) = 0
          OR COALESCE(l.latest_rows_with_macd_histogram, 0) = 0 THEN 'MISSING_SHORT_NUMERICS'
        ELSE 'OK'
    END AS freshness_status
FROM expected_bar e
LEFT JOIN ohlcv_latest o
  ON o.timeframe = e.timeframe
LEFT JOIN feature_latest f
  ON f.timeframe = e.timeframe
LEFT JOIN latest_feature_rows l
  ON l.timeframe = e.timeframe
ORDER BY
    CASE e.timeframe
        WHEN '1m' THEN 1
        WHEN '5m' THEN 2
        WHEN '15m' THEN 3
        WHEN '30m' THEN 4
        WHEN '1H' THEN 5
        WHEN '4H' THEN 6
        WHEN '1D' THEN 7
        ELSE 999
    END;
