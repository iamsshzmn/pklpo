-- Добавление недостающих колонок в таблицу indicators

-- Добавляем колонки для overlap индикаторов
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS "hl2" NUMERIC;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS "hlc3" NUMERIC;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS "ohlc4" NUMERIC;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS "wcp" NUMERIC;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS "midpoint" NUMERIC;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS "midprice" NUMERIC;

-- Проверяем результат
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'indicators'
AND table_schema = 'public'
AND column_name IN ('hl2', 'hlc3', 'ohlc4', 'wcp', 'midpoint', 'midprice')
ORDER BY column_name;
