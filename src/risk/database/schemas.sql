-- Создание таблиц для guard'ов, алертов, метрик, лимитов, нарушений и логов сайзинга

-- Схема risk
-- Необходимо расширение pgcrypto для gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS risk;

-- Таблица зарегистрированных guards
CREATE TABLE IF NOT EXISTS risk.guards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('circuit_breaker','killswitch','dq_guard','sla_guard','health_guard')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('active','triggered','disabled','maintenance')),
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT guards_name_type_unique UNIQUE (name, type)
);

-- История состояний guards
CREATE TABLE IF NOT EXISTS risk.guard_state_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guard_id UUID NOT NULL REFERENCES risk.guards(id) ON DELETE CASCADE,
    state VARCHAR(20) NOT NULL CHECK (state IN ('closed','opened','half_open','enabled','disabled','emergency')),
    trigger_count INTEGER NOT NULL DEFAULT 0,
    last_triggered TIMESTAMPTZ,
    last_recovery TIMESTAMPTZ,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Алерты от guards
CREATE TABLE IF NOT EXISTS risk.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guard_id UUID REFERENCES risk.guards(id) ON DELETE SET NULL,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    message TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Метрики guard'ов и системы (временные ряды)
CREATE TABLE IF NOT EXISTS risk.metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guard_id UUID REFERENCES risk.guards(id) ON DELETE SET NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC(20,6) NOT NULL,
    labels JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Лимиты риска (конфигурация)
CREATE TABLE IF NOT EXISTS risk.limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('daily_loss','weekly_loss','max_concurrent','max_corr','cooldown')),
    value NUMERIC(20,6) NOT NULL,
    time_window VARCHAR(50), -- например: '1d', '1w'
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT limits_name_unique UNIQUE (name)
);

-- Зафиксированные нарушения (violations)
CREATE TABLE IF NOT EXISTS risk.violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100) NOT NULL,   -- модуль/guard/валидация
    code VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Логи расчета размера позиции (sizing)
CREATE TABLE IF NOT EXISTS risk.sizing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id INTEGER,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    entry NUMERIC(20,8) NOT NULL,
    stop NUMERIC(20,8) NOT NULL,
    take NUMERIC(20,8),
    balance NUMERIC(20,8) NOT NULL,
    risk_pct NUMERIC(10,6) NOT NULL,
    size NUMERIC(30,10) NOT NULL,          -- количество контрактов/монет
    notional NUMERIC(30,10) NOT NULL,      -- номинал
    fees NUMERIC(20,8) DEFAULT 0,
    slippage NUMERIC(20,8) DEFAULT 0,
    lot_size NUMERIC(20,10) DEFAULT 0,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Показатели здоровья системы (snapshots)
CREATE TABLE IF NOT EXISTS risk.system_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cpu_percent NUMERIC(6,2),
    memory_percent NUMERIC(6,2),
    disk_percent NUMERIC(6,2),
    connections INTEGER,
    status VARCHAR(20),
    run_id VARCHAR(100) NOT NULL DEFAULT '',
    algo_version VARCHAR(50) NOT NULL DEFAULT '',
    params_hash VARCHAR(64) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Представление активных guards
CREATE OR REPLACE VIEW risk.active_guards AS
SELECT id, name, type, status, config, created_at, updated_at
FROM risk.guards
WHERE status = 'active';

-- Представление ежедневных алертов
CREATE OR REPLACE VIEW risk.daily_alerts AS
SELECT
    DATE(created_at) AS date,
    severity,
    COUNT(*) AS count
FROM risk.alerts
GROUP BY DATE(created_at), severity
ORDER BY date DESC;

-- Представление сводки нарушений
CREATE OR REPLACE VIEW risk.violations_summary AS
SELECT
    source,
    code,
    severity,
    COUNT(*) AS total
FROM risk.violations
GROUP BY source, code, severity
ORDER BY total DESC;

-- Индексы
CREATE INDEX IF NOT EXISTS idx_guards_type ON risk.guards(type);
CREATE INDEX IF NOT EXISTS idx_guards_status ON risk.guards(status);
CREATE INDEX IF NOT EXISTS idx_guard_state_history_guard_id ON risk.guard_state_history(guard_id);
CREATE INDEX IF NOT EXISTS idx_alerts_guard_id ON risk.alerts(guard_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON risk.alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_severity_created_at ON risk.alerts(severity, created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_guard_id ON risk.metrics(guard_id);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON risk.metrics(ts);
CREATE INDEX IF NOT EXISTS idx_limits_enabled ON risk.limits(enabled);
CREATE INDEX IF NOT EXISTS idx_violations_created_at ON risk.violations(created_at);
CREATE INDEX IF NOT EXISTS idx_sizing_logs_symbol_ts ON risk.sizing_logs(symbol_id, ts);
CREATE INDEX IF NOT EXISTS idx_system_health_ts ON risk.system_health(ts);
CREATE INDEX IF NOT EXISTS idx_guard_state_history_created_at ON risk.guard_state_history(created_at);

-- Функция очистки старых данных risk
CREATE OR REPLACE FUNCTION risk.cleanup_old_data(
    days_to_keep_alerts INTEGER DEFAULT 90,
    days_to_keep_metrics INTEGER DEFAULT 90,
    days_to_keep_violations INTEGER DEFAULT 180,
    days_to_keep_health INTEGER DEFAULT 30,
    days_to_keep_sizing INTEGER DEFAULT 30,
    days_to_keep_guard_state INTEGER DEFAULT 90,
    batch_size INTEGER DEFAULT 10000
)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    _c INTEGER := 0;
BEGIN
    -- alerts
    LOOP
        WITH old_rows AS (
            SELECT id FROM risk.alerts
            WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep_alerts
            LIMIT batch_size
        ), del AS (
            DELETE FROM risk.alerts a USING old_rows o WHERE a.id = o.id RETURNING 1
        ) SELECT COALESCE(COUNT(*),0) INTO _c FROM del;
        EXIT WHEN _c = 0;
        deleted_count := deleted_count + _c;
    END LOOP;

    -- metrics
    LOOP
        WITH old_rows AS (
            SELECT id FROM risk.metrics
            WHERE ts < NOW() - INTERVAL '1 day' * days_to_keep_metrics
            LIMIT batch_size
        ), del AS (
            DELETE FROM risk.metrics m USING old_rows o WHERE m.id = o.id RETURNING 1
        ) SELECT COALESCE(COUNT(*),0) INTO _c FROM del;
        EXIT WHEN _c = 0;
        deleted_count := deleted_count + _c;
    END LOOP;

    -- violations
    LOOP
        WITH old_rows AS (
            SELECT id FROM risk.violations
            WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep_violations
            LIMIT batch_size
        ), del AS (
            DELETE FROM risk.violations v USING old_rows o WHERE v.id = o.id RETURNING 1
        ) SELECT COALESCE(COUNT(*),0) INTO _c FROM del;
        EXIT WHEN _c = 0;
        deleted_count := deleted_count + _c;
    END LOOP;

    -- system_health
    LOOP
        WITH old_rows AS (
            SELECT id FROM risk.system_health
            WHERE ts < NOW() - INTERVAL '1 day' * days_to_keep_health
            LIMIT batch_size
        ), del AS (
            DELETE FROM risk.system_health s USING old_rows o WHERE s.id = o.id RETURNING 1
        ) SELECT COALESCE(COUNT(*),0) INTO _c FROM del;
        EXIT WHEN _c = 0;
        deleted_count := deleted_count + _c;
    END LOOP;

    -- sizing_logs
    LOOP
        WITH old_rows AS (
            SELECT id FROM risk.sizing_logs
            WHERE ts < NOW() - INTERVAL '1 day' * days_to_keep_sizing
            LIMIT batch_size
        ), del AS (
            DELETE FROM risk.sizing_logs s USING old_rows o WHERE s.id = o.id RETURNING 1
        ) SELECT COALESCE(COUNT(*),0) INTO _c FROM del;
        EXIT WHEN _c = 0;
        deleted_count := deleted_count + _c;
    END LOOP;

    -- guard_state_history
    LOOP
        WITH old_rows AS (
            SELECT id FROM risk.guard_state_history
            WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep_guard_state
            LIMIT batch_size
        ), del AS (
            DELETE FROM risk.guard_state_history g USING old_rows o WHERE g.id = o.id RETURNING 1
        ) SELECT COALESCE(COUNT(*),0) INTO _c FROM del;
        EXIT WHEN _c = 0;
        deleted_count := deleted_count + _c;
    END LOOP;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция статистики по guard'у
CREATE OR REPLACE FUNCTION risk.get_guard_stats(p_guard_id UUID)
RETURNS TABLE (
    last_state VARCHAR,
    total_alerts BIGINT,
    last_alert_at TIMESTAMPTZ,
    avg_metric NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT state FROM risk.guard_state_history WHERE guard_id = p_guard_id ORDER BY created_at DESC LIMIT 1) AS last_state,
        (SELECT COUNT(*) FROM risk.alerts WHERE guard_id = p_guard_id) AS total_alerts,
        (SELECT MAX(created_at) FROM risk.alerts WHERE guard_id = p_guard_id) AS last_alert_at,
        (SELECT AVG(metric_value) FROM risk.metrics WHERE guard_id = p_guard_id) AS avg_metric;
END;
$$ LANGUAGE plpgsql;

-- Триггеры обновления updated_at
CREATE OR REPLACE FUNCTION risk.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'tr_guards_set_updated_at'
    ) THEN
        CREATE TRIGGER tr_guards_set_updated_at
        BEFORE UPDATE ON risk.guards
        FOR EACH ROW
        EXECUTE FUNCTION risk.set_updated_at();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'tr_limits_set_updated_at'
    ) THEN
        CREATE TRIGGER tr_limits_set_updated_at
        BEFORE UPDATE ON risk.limits
        FOR EACH ROW
        EXECUTE FUNCTION risk.set_updated_at();
    END IF;
END$$;

-- Комментарии
COMMENT ON SCHEMA risk IS 'Схема для модуля управления рисками';
COMMENT ON TABLE risk.guards IS 'Зарегистрированные предохранители (guards)';
COMMENT ON TABLE risk.guard_state_history IS 'История состояний guard''ов';
COMMENT ON TABLE risk.alerts IS 'Алерты, созданные guard''ами';
COMMENT ON TABLE risk.metrics IS 'Метрики guard''ов и системы';
COMMENT ON TABLE risk.limits IS 'Конфигурация риск-лимитов';
COMMENT ON TABLE risk.violations IS 'Зарегистрированные нарушения и сбои';
COMMENT ON TABLE risk.sizing_logs IS 'Логи расчета размера позиции';
COMMENT ON TABLE risk.system_health IS 'Снапшоты состояния системы';
