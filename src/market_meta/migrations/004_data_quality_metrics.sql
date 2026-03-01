-- Migration: 004_data_quality_metrics
-- Description: Таблица метрик качества данных для мониторинга
-- Date: 2024-12-18

-- Схема ops (если не существует)
CREATE SCHEMA IF NOT EXISTS ops;

-- Таблица метрик качества данных
CREATE TABLE IF NOT EXISTS ops.data_quality_metrics (
    id BIGSERIAL PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name TEXT NOT NULL,           -- freshness / coverage / fill_rate / smoke
    severity TEXT NOT NULL,             -- ok / warn / critical
    symbol TEXT NULL,
    timeframe TEXT NULL,
    value NUMERIC NULL,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Индексы для быстрых запросов
CREATE INDEX IF NOT EXISTS ix_dq_metrics_ts
    ON ops.data_quality_metrics (ts DESC);

CREATE INDEX IF NOT EXISTS ix_dq_metrics_check
    ON ops.data_quality_metrics (check_name, ts DESC);

CREATE INDEX IF NOT EXISTS ix_dq_metrics_severity
    ON ops.data_quality_metrics (severity, ts DESC)
    WHERE severity IN ('warn', 'critical');

-- Комментарии
COMMENT ON TABLE ops.data_quality_metrics IS 'Метрики качества данных market_data_ext';
COMMENT ON COLUMN ops.data_quality_metrics.check_name IS 'Тип проверки: freshness, coverage, fill_rate, smoke, event_freshness';
COMMENT ON COLUMN ops.data_quality_metrics.severity IS 'Уровень: ok, warn, critical';
COMMENT ON COLUMN ops.data_quality_metrics.value IS 'Числовое значение метрики (lag_min, coverage_pct, fill_pct)';
COMMENT ON COLUMN ops.data_quality_metrics.meta IS 'Дополнительные данные: пороги, детали проверки';
