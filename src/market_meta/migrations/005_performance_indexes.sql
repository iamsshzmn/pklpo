-- Миграция 005: Индексы для оптимизации производительности (Фаза 5)
-- Автор: PKLPO Team
-- Дата: 2024-12-18

-- ============================================================================
-- RAW: raw.market_data_ext_raw
-- Цель: быстрый выбор "тип + символ + окно"
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_ext_raw_type_symbol_ts
  ON raw.market_data_ext_raw (data_type, symbol, ts DESC);

-- BRIN по времени (эффективен если вставки идут по времени)
CREATE INDEX IF NOT EXISTS brin_ext_raw_ts
  ON raw.market_data_ext_raw USING brin (ts);

-- ============================================================================
-- CORE: core.market_data_ext
-- Цель: validate (последние N минут), агрегация по окнам, запросы по symbol/tf
-- ============================================================================

CREATE INDEX IF NOT EXISTS ix_ext_core_tf_ts
  ON core.market_data_ext (timeframe, bar_timestamp DESC);

CREATE INDEX IF NOT EXISTS ix_ext_core_symbol_tf_ts
  ON core.market_data_ext (symbol, timeframe, bar_timestamp DESC);

-- ============================================================================
-- ANALYZE для обновления статистики
-- ============================================================================

ANALYZE raw.market_data_ext_raw;
ANALYZE core.market_data_ext;
