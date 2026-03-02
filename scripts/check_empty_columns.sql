-- Проверка пустых колонок в таблице indicators
-- Использование: psql -d pklpo -f scripts/check_empty_columns.sql

-- 1) Список всех колонок и их типов
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'indicators'
  AND column_name NOT IN ('symbol', 'timeframe', 'timestamp', 'calculated_at', 'created_at', 'updated_at')
ORDER BY column_name;

-- 2) Пустые колонки за последние 2 дня
WITH recent_data AS (
  SELECT *
  FROM indicators
  WHERE timestamp >= EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC' - INTERVAL '2 days')) * 1000
)
SELECT
    c.column_name,
    COUNT(*) as total_rows,
    COUNT(r.*) FILTER (WHERE r IS NOT NULL) as non_null_rows,
    100.0 * COUNT(r.*) FILTER (WHERE r IS NOT NULL) / COUNT(*) as fill_rate
FROM information_schema.columns c
CROSS JOIN recent_data rd
LEFT JOIN LATERAL (
    SELECT CASE
        WHEN c.column_name = 'bb_upper' THEN rd.bb_upper
        WHEN c.column_name = 'bb_middle' THEN rd.bb_middle
        WHEN c.column_name = 'bb_lower' THEN rd.bb_lower
        WHEN c.column_name = 'hlc3' THEN rd.hlc3
        WHEN c.column_name = 'hl2' THEN rd.hl2
        WHEN c.column_name = 'ohlc4' THEN rd.ohlc4
        -- Добавьте другие колонки по необходимости
        ELSE NULL
    END as r
) r ON true
WHERE c.table_name = 'indicators'
  AND c.table_schema = 'public'
  AND c.column_name NOT IN ('symbol', 'timeframe', 'timestamp', 'calculated_at', 'created_at', 'updated_at')
GROUP BY c.column_name
HAVING COUNT(r.*) FILTER (WHERE r IS NOT NULL) = 0
ORDER BY c.column_name;

-- 3) Заполненность критических колонок
SELECT
    symbol,
    timeframe,
    100.0 * SUM((bb_upper IS NOT NULL)::int) / COUNT(*) AS bb_upper_fill,
    100.0 * SUM((bb_middle IS NOT NULL)::int) / COUNT(*) AS bb_middle_fill,
    100.0 * SUM((bb_lower IS NOT NULL)::int) / COUNT(*) AS bb_lower_fill,
    100.0 * SUM((hlc3 IS NOT NULL)::int) / COUNT(*) AS hlc3_fill,
    100.0 * SUM((hl2 IS NOT NULL)::int) / COUNT(*) AS hl2_fill,
    100.0 * SUM((ohlc4 IS NOT NULL)::int) / COUNT(*) AS ohlc4_fill,
    100.0 * SUM((ichimoku_tenkan IS NOT NULL)::int) / COUNT(*) AS ichimoku_tenkan_fill,
    100.0 * SUM((ichimoku_kijun IS NOT NULL)::int) / COUNT(*) AS ichimoku_kijun_fill,
    COUNT(*) as total_rows
FROM indicators
WHERE timestamp >= EXTRACT(EPOCH FROM (NOW() AT TIME ZONE 'UTC' - INTERVAL '2 days')) * 1000
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;
