-- Пересчёт willr и ultosc для записей с NULL

-- 1. Обновление willr
WITH ohlcv_data AS (
    SELECT
        o.timestamp,
        o.high,
        o.low,
        o.close,
        MAX(o.high) OVER (PARTITION BY o.symbol, o.timeframe ORDER BY o.timestamp ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as highest_high_14,
        MIN(o.low) OVER (PARTITION BY o.symbol, o.timeframe ORDER BY o.timestamp ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as lowest_low_14
    FROM swap_ohlcv_p o
    WHERE o.symbol = 'BTC-USDT-SWAP' AND o.timeframe = '1m'
),
willr_calc AS (
    SELECT
        timestamp,
        CASE
            WHEN highest_high_14 - lowest_low_14 > 0
            THEN -100.0 * (highest_high_14 - close) / (highest_high_14 - lowest_low_14)
            ELSE NULL
        END as willr
    FROM ohlcv_data
)
UPDATE indicators i
SET willr = w.willr
FROM willr_calc w
WHERE i.symbol = 'BTC-USDT-SWAP'
    AND i.timeframe = '1m'
    AND i.timestamp = w.timestamp
    AND i.willr IS NULL
    AND w.willr IS NOT NULL;

-- 2. Обновление ultosc
WITH ohlcv_data AS (
    SELECT
        o.timestamp,
        o.high,
        o.low,
        o.close,
        LAG(o.close) OVER (PARTITION BY o.symbol, o.timeframe ORDER BY o.timestamp) as prev_close
    FROM swap_ohlcv_p o
    WHERE o.symbol = 'BTC-USDT-SWAP' AND o.timeframe = '1m'
),
bp_tr AS (
    SELECT
        timestamp,
        -- Buying Pressure
        close - LEAST(low, COALESCE(prev_close, low)) as bp,
        -- True Range
        GREATEST(
            high - low,
            ABS(high - COALESCE(prev_close, high)),
            ABS(low - COALESCE(prev_close, low))
        ) as tr
    FROM ohlcv_data
),
ultosc_calc AS (
    SELECT
        timestamp,
        bp,
        tr,
        SUM(bp) OVER (ORDER BY timestamp ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as bp_sum_7,
        SUM(tr) OVER (ORDER BY timestamp ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as tr_sum_7,
        SUM(bp) OVER (ORDER BY timestamp ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as bp_sum_14,
        SUM(tr) OVER (ORDER BY timestamp ROWS BETWEEN 13 PRECEDING AND CURRENT ROW) as tr_sum_14,
        SUM(bp) OVER (ORDER BY timestamp ROWS BETWEEN 27 PRECEDING AND CURRENT ROW) as bp_sum_28,
        SUM(tr) OVER (ORDER BY timestamp ROWS BETWEEN 27 PRECEDING AND CURRENT ROW) as tr_sum_28
    FROM bp_tr
),
ultosc_final AS (
    SELECT
        timestamp,
        CASE
            WHEN tr_sum_7 > 0 AND tr_sum_14 > 0 AND tr_sum_28 > 0
            THEN 100.0 * (4.0 * (bp_sum_7 / tr_sum_7) + 2.0 * (bp_sum_14 / tr_sum_14) + (bp_sum_28 / tr_sum_28)) / 7.0
            ELSE NULL
        END as ultosc
    FROM ultosc_calc
)
UPDATE indicators i
SET ultosc = u.ultosc
FROM ultosc_final u
WHERE i.symbol = 'BTC-USDT-SWAP'
    AND i.timeframe = '1m'
    AND i.timestamp = u.timestamp
    AND i.ultosc IS NULL
    AND u.ultosc IS NOT NULL;

-- Проверка результата
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN willr IS NOT NULL THEN 1 END) as willr_filled,
    COUNT(CASE WHEN ultosc IS NOT NULL THEN 1 END) as ultosc_filled
FROM indicators
WHERE symbol = 'BTC-USDT-SWAP' AND timeframe = '1m';
