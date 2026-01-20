-- Добавление недостающих колонок в таблицу indicators
-- Использование: psql -d pklpo -f scripts/add_missing_columns.sql

-- Bollinger Bands (если используются bb_* вместо bbands_*)
DO $$
BEGIN
    -- Проверяем и добавляем bb_* колонки
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'indicators'
          AND column_name = 'bb_upper'
    ) THEN
        ALTER TABLE public.indicators
        ADD COLUMN bb_upper DOUBLE PRECISION,
        ADD COLUMN bb_middle DOUBLE PRECISION,
        ADD COLUMN bb_lower DOUBLE PRECISION;
        RAISE NOTICE 'Added bb_upper, bb_middle, bb_lower columns';
    END IF;

    -- Если есть bbands_* колонки, переименовываем их
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'indicators'
          AND column_name = 'bbands_upper'
    ) THEN
        ALTER TABLE public.indicators RENAME COLUMN bbands_upper TO bb_upper;
        ALTER TABLE public.indicators RENAME COLUMN bbands_middle TO bb_middle;
        ALTER TABLE public.indicators RENAME COLUMN bbands_lower TO bb_lower;
        RAISE NOTICE 'Renamed bbands_* to bb_* columns';
    END IF;
END $$;

-- Overlap индикаторы
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'indicators'
          AND column_name = 'hl2'
    ) THEN
        ALTER TABLE public.indicators
        ADD COLUMN hl2 DOUBLE PRECISION,
        ADD COLUMN hlc3 DOUBLE PRECISION,
        ADD COLUMN ohlc4 DOUBLE PRECISION;
        RAISE NOTICE 'Added hl2, hlc3, ohlc4 columns';
    END IF;
END $$;

-- Ichimoku индикаторы (если отсутствуют)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'indicators'
          AND column_name = 'ichimoku_tenkan'
    ) THEN
        ALTER TABLE public.indicators
        ADD COLUMN ichimoku_tenkan DOUBLE PRECISION,
        ADD COLUMN ichimoku_kijun DOUBLE PRECISION,
        ADD COLUMN ichimoku_senkou_a DOUBLE PRECISION,
        ADD COLUMN ichimoku_senkou_b DOUBLE PRECISION,
        ADD COLUMN ichimoku_chikou DOUBLE PRECISION;
        RAISE NOTICE 'Added ichimoku_* columns';
    END IF;
END $$;

-- Проверка результата
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'indicators'
  AND column_name IN (
    'bb_upper', 'bb_middle', 'bb_lower',
    'hl2', 'hlc3', 'ohlc4',
    'ichimoku_tenkan', 'ichimoku_kijun',
    'ichimoku_senkou_a', 'ichimoku_senkou_b', 'ichimoku_chikou'
  )
ORDER BY column_name;
