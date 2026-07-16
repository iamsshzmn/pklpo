\set ON_ERROR_STOP on

-- Check 1: contract specs available in instruments.
SELECT
    o.symbol AS old_symbol,
    n.symbol AS new_symbol,
    o.ct_val,
    n.ct_val,
    o.ct_type,
    n.ct_type,
    o.ct_val_ccy,
    n.ct_val_ccy,
    o.settle_ccy,
    n.settle_ccy,
    o.min_sz,
    n.min_sz,
    (
        o.ct_val IS NOT DISTINCT FROM n.ct_val
        AND o.ct_type IS NOT DISTINCT FROM n.ct_type
        AND o.ct_val_ccy IS NOT DISTINCT FROM n.ct_val_ccy
        AND o.settle_ccy IS NOT DISTINCT FROM n.settle_ccy
        AND o.min_sz IS NOT DISTINCT FROM n.min_sz
    ) AS specs_match
FROM instruments o
CROSS JOIN instruments n
WHERE o.symbol='TON-USDT-SWAP'
  AND n.symbol='GRAM-USDT-SWAP';

-- Check 2a: raw timestamp unit sanity. swap_ohlcv_p.timestamp is expected in ms.
SELECT
    symbol,
    min(timestamp) AS min_timestamp,
    max(timestamp) AS max_timestamp,
    to_timestamp(min(timestamp) / 1000.0) AS min_timestamp_utc,
    to_timestamp(max(timestamp) / 1000.0) AS max_timestamp_utc
FROM swap_ohlcv_p
WHERE symbol IN ('TON-USDT-SWAP', 'GRAM-USDT-SWAP')
GROUP BY symbol
ORDER BY symbol;

-- Check 2b: price continuity at the TON->GRAM stitch point, ratio=1.
WITH last_old AS (
    SELECT close AS old_close, timestamp AS old_ts
    FROM swap_ohlcv_p
    WHERE symbol='TON-USDT-SWAP'
      AND timeframe='1H'
    ORDER BY timestamp DESC
    LIMIT 1
),
first_new AS (
    SELECT close AS new_close, timestamp AS new_ts
    FROM swap_ohlcv_p
    WHERE symbol='GRAM-USDT-SWAP'
      AND timeframe='1H'
    ORDER BY timestamp ASC
    LIMIT 1
)
SELECT
    l.old_close,
    f.new_close,
    to_timestamp(l.old_ts / 1000.0) AS old_last_bar,
    to_timestamp(f.new_ts / 1000.0) AS new_first_bar,
    (f.new_ts - l.old_ts) / 3600000.0 AS gap_hours,
    abs(f.new_close - l.old_close) / nullif(l.old_close, 0) AS rel_jump,
    (abs(f.new_close - l.old_close) / nullif(l.old_close, 0) < 0.05) AS continuity_ok
FROM last_old l
CROSS JOIN first_new f;

-- Manual approve only when specs_match=true AND continuity_ok=true:
-- UPDATE ops.symbol_succession SET status='approved',
--     contract_specs_checked=true,
--     price_continuity_checked=true,
--     updated_at=now()
-- WHERE venue='OKX'
--   AND inst_type='SWAP'
--   AND old_symbol='TON-USDT-SWAP'
--   AND new_symbol='GRAM-USDT-SWAP';
