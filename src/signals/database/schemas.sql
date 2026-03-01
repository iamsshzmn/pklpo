-- Схемы базы данных для модуля Signals (Фаза 4)
-- Создание таблиц для candidates, live, history

-- Схема signals
CREATE SCHEMA IF NOT EXISTS signals;

-- Таблица кандидатов на торговые сигналы
CREATE TABLE IF NOT EXISTS signals.candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id INTEGER NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon VARCHAR(20) NOT NULL CHECK (horizon IN ('intraday', 'swing', 'week')),
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short', 'flat')),
    entry DECIMAL(20, 8) NOT NULL,
    stop DECIMAL(20, 8) NOT NULL,
    take DECIMAL(20, 8) NOT NULL,
    ttl_sec INTEGER NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    expected_r DECIMAL(10, 6) NOT NULL,
    rationale TEXT[] NOT NULL,
    algo_version VARCHAR(50) NOT NULL,
    params_hash VARCHAR(64) NOT NULL,
    run_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'validated', 'rejected')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    validated_at TIMESTAMP WITH TIME ZONE,
    validation_results JSONB,

    -- Индексы
    CONSTRAINT candidates_symbol_ts_idx UNIQUE (symbol_id, ts),
    CONSTRAINT candidates_run_id_idx UNIQUE (run_id, symbol_id)
);

-- Таблица активных торговых сигналов
CREATE TABLE IF NOT EXISTS signals.live (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID NOT NULL REFERENCES signals.candidates(id),
    symbol_id INTEGER NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon VARCHAR(20) NOT NULL CHECK (horizon IN ('intraday', 'swing', 'week')),
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short', 'flat')),
    entry DECIMAL(20, 8) NOT NULL,
    stop DECIMAL(20, 8) NOT NULL,
    take DECIMAL(20, 8) NOT NULL,
    ttl_sec INTEGER NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    expected_r DECIMAL(10, 6) NOT NULL,
    rationale TEXT[] NOT NULL,
    algo_version VARCHAR(50) NOT NULL,
    params_hash VARCHAR(64) NOT NULL,
    run_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'live' CHECK (status IN ('live', 'expired', 'cancelled', 'executed', 'failed')),
    activated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    executed_at TIMESTAMP WITH TIME ZONE,
    execution_metrics JSONB,

    -- Индексы
    CONSTRAINT live_candidate_id_idx UNIQUE (candidate_id),
    CONSTRAINT live_symbol_activated_idx UNIQUE (symbol_id, activated_at)
);

-- Таблица истории исполненных сигналов
CREATE TABLE IF NOT EXISTS signals.history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    live_id UUID NOT NULL REFERENCES signals.live(id),
    symbol_id INTEGER NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon VARCHAR(20) NOT NULL CHECK (horizon IN ('intraday', 'swing', 'week')),
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short', 'flat')),
    entry DECIMAL(20, 8) NOT NULL,
    stop DECIMAL(20, 8) NOT NULL,
    take DECIMAL(20, 8) NOT NULL,
    ttl_sec INTEGER NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    expected_r DECIMAL(10, 6) NOT NULL,
    actual_r DECIMAL(10, 6) NOT NULL,
    rationale TEXT[] NOT NULL,
    algo_version VARCHAR(50) NOT NULL,
    params_hash VARCHAR(64) NOT NULL,
    run_id VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('expired', 'cancelled', 'executed', 'failed')),
    activated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    execution_metrics JSONB,
    performance_metrics JSONB,

    -- Индексы
    CONSTRAINT history_live_id_idx UNIQUE (live_id)
);

-- Таблица метрик производительности сигналов
CREATE TABLE IF NOT EXISTS signals.metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id INTEGER,
    date DATE NOT NULL,
    total_generated INTEGER NOT NULL DEFAULT 0,
    total_validated INTEGER NOT NULL DEFAULT 0,
    total_promoted INTEGER NOT NULL DEFAULT 0,
    total_executed INTEGER NOT NULL DEFAULT 0,
    total_failed INTEGER NOT NULL DEFAULT 0,
    validation_pass_rate DECIMAL(5, 4) NOT NULL DEFAULT 0,
    promotion_rate DECIMAL(5, 4) NOT NULL DEFAULT 0,
    execution_success_rate DECIMAL(5, 4) NOT NULL DEFAULT 0,
    avg_expected_r DECIMAL(10, 6) NOT NULL DEFAULT 0,
    avg_actual_r DECIMAL(10, 6) NOT NULL DEFAULT 0,
    avg_confidence DECIMAL(5, 4) NOT NULL DEFAULT 0,
    avg_execution_time_sec DECIMAL(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Индексы
    CONSTRAINT metrics_symbol_date_idx UNIQUE (symbol_id, date)
);

-- Представления для удобного доступа к данным

-- Представление активных сигналов с метаданными
CREATE OR REPLACE VIEW signals.active_signals AS
SELECT
    l.id,
    l.symbol_id,
    l.ts,
    l.horizon,
    l.side,
    l.entry,
    l.stop,
    l.take,
    l.confidence,
    l.expected_r,
    l.activated_at,
    l.expires_at,
    l.execution_metrics,
    EXTRACT(EPOCH FROM (l.expires_at - NOW())) as time_to_expire_sec,
    CASE
        WHEN l.expires_at < NOW() THEN 'expired'
        ELSE 'active'
    END as current_status
FROM signals.live l
WHERE l.status = 'live';

-- Представление статистики сигналов по символам
CREATE OR REPLACE VIEW signals.symbol_stats AS
SELECT
    symbol_id,
    COUNT(*) as total_signals,
    COUNT(CASE WHEN status = 'executed' THEN 1 END) as executed_count,
    COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_count,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,
    AVG(confidence) as avg_confidence,
    AVG(expected_r) as avg_expected_r,
    AVG(actual_r) as avg_actual_r,
    AVG(actual_r - expected_r) as avg_r_difference,
    MIN(activated_at) as first_signal_at,
    MAX(activated_at) as last_signal_at
FROM signals.history
GROUP BY symbol_id;

-- Представление дневной статистики
CREATE OR REPLACE VIEW signals.daily_stats AS
SELECT
    DATE(activated_at) as date,
    COUNT(*) as total_signals,
    COUNT(CASE WHEN status = 'executed' THEN 1 END) as executed_count,
    COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_count,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,
    AVG(confidence) as avg_confidence,
    AVG(expected_r) as avg_expected_r,
    AVG(actual_r) as avg_actual_r,
    AVG(actual_r - expected_r) as avg_r_difference
FROM signals.history
GROUP BY DATE(activated_at)
ORDER BY date DESC;

-- Индексы для оптимизации запросов

-- Индексы для candidates
CREATE INDEX IF NOT EXISTS idx_candidates_symbol_id ON signals.candidates(symbol_id);
CREATE INDEX IF NOT EXISTS idx_candidates_ts ON signals.candidates(ts);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON signals.candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_created_at ON signals.candidates(created_at);
CREATE INDEX IF NOT EXISTS idx_candidates_run_id ON signals.candidates(run_id);

-- Индексы для live
CREATE INDEX IF NOT EXISTS idx_live_symbol_id ON signals.live(symbol_id);
CREATE INDEX IF NOT EXISTS idx_live_status ON signals.live(status);
CREATE INDEX IF NOT EXISTS idx_live_activated_at ON signals.live(activated_at);
CREATE INDEX IF NOT EXISTS idx_live_expires_at ON signals.live(expires_at);
CREATE INDEX IF NOT EXISTS idx_live_candidate_id ON signals.live(candidate_id);

-- Индексы для history
CREATE INDEX IF NOT EXISTS idx_history_symbol_id ON signals.history(symbol_id);
CREATE INDEX IF NOT EXISTS idx_history_activated_at ON signals.history(activated_at);
CREATE INDEX IF NOT EXISTS idx_history_executed_at ON signals.history(executed_at);
CREATE INDEX IF NOT EXISTS idx_history_status ON signals.history(status);
CREATE INDEX IF NOT EXISTS idx_history_live_id ON signals.history(live_id);

-- Индексы для metrics
CREATE INDEX IF NOT EXISTS idx_metrics_symbol_id ON signals.metrics(symbol_id);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON signals.metrics(date);

-- Функции для работы с сигналами

-- Функция очистки старых данных
CREATE OR REPLACE FUNCTION signals.cleanup_old_data(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Удаляем старые записи из history
    DELETE FROM signals.history
    WHERE executed_at < NOW() - INTERVAL '1 day' * days_to_keep;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Удаляем старые записи из candidates (только отклоненные)
    DELETE FROM signals.candidates
    WHERE status = 'rejected'
    AND created_at < NOW() - INTERVAL '1 day' * days_to_keep;

    GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Функция получения статистики по символу
CREATE OR REPLACE FUNCTION signals.get_symbol_stats(p_symbol_id INTEGER)
RETURNS TABLE (
    total_signals BIGINT,
    executed_count BIGINT,
    expired_count BIGINT,
    cancelled_count BIGINT,
    avg_confidence NUMERIC,
    avg_expected_r NUMERIC,
    avg_actual_r NUMERIC,
    avg_r_difference NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_signals,
        COUNT(CASE WHEN status = 'executed' THEN 1 END) as executed_count,
        COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_count,
        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,
        AVG(confidence) as avg_confidence,
        AVG(expected_r) as avg_expected_r,
        AVG(actual_r) as avg_actual_r,
        AVG(actual_r - expected_r) as avg_r_difference
    FROM signals.history
    WHERE symbol_id = p_symbol_id;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для автоматического обновления метрик

-- Триггер для обновления метрик при создании candidate
CREATE OR REPLACE FUNCTION signals.update_metrics_on_candidate()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO signals.metrics (symbol_id, date, total_generated)
    VALUES (NEW.symbol_id, CURRENT_DATE, 1)
    ON CONFLICT (symbol_id, date)
    DO UPDATE SET
        total_generated = signals.metrics.total_generated + 1;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_metrics_on_candidate
    AFTER INSERT ON signals.candidates
    FOR EACH ROW
    EXECUTE FUNCTION signals.update_metrics_on_candidate();

-- Триггер для обновления метрик при изменении статуса candidate
CREATE OR REPLACE FUNCTION signals.update_metrics_on_candidate_status()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status != NEW.status THEN
        IF NEW.status = 'validated' THEN
            UPDATE signals.metrics
            SET total_validated = total_validated + 1
            WHERE symbol_id = NEW.symbol_id AND date = CURRENT_DATE;
        ELSIF NEW.status = 'rejected' THEN
            UPDATE signals.metrics
            SET total_validated = total_validated - 1
            WHERE symbol_id = NEW.symbol_id AND date = CURRENT_DATE;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_metrics_on_candidate_status
    AFTER UPDATE ON signals.candidates
    FOR EACH ROW
    EXECUTE FUNCTION signals.update_metrics_on_candidate_status();

-- Триггер для обновления метрик при создании live сигнала
CREATE OR REPLACE FUNCTION signals.update_metrics_on_live()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE signals.metrics
    SET total_promoted = total_promoted + 1
    WHERE symbol_id = NEW.symbol_id AND date = CURRENT_DATE;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_metrics_on_live
    AFTER INSERT ON signals.live
    FOR EACH ROW
    EXECUTE FUNCTION signals.update_metrics_on_live();

-- Триггер для обновления метрик при создании history записи
CREATE OR REPLACE FUNCTION signals.update_metrics_on_history()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'executed' THEN
        UPDATE signals.metrics
        SET
            total_executed = total_executed + 1,
            avg_expected_r = (avg_expected_r * (total_executed - 1) + NEW.expected_r) / total_executed,
            avg_actual_r = (avg_actual_r * (total_executed - 1) + NEW.actual_r) / total_executed
        WHERE symbol_id = NEW.symbol_id AND date = CURRENT_DATE;
    ELSE
        UPDATE signals.metrics
        SET total_failed = total_failed + 1
        WHERE symbol_id = NEW.symbol_id AND date = CURRENT_DATE;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_metrics_on_history
    AFTER INSERT ON signals.history
    FOR EACH ROW
    EXECUTE FUNCTION signals.update_metrics_on_history();

-- Комментарии к таблицам
COMMENT ON SCHEMA signals IS 'Схема для модуля торговых сигналов';
COMMENT ON TABLE signals.candidates IS 'Кандидаты на торговые сигналы';
COMMENT ON TABLE signals.live IS 'Активные торговые сигналы';
COMMENT ON TABLE signals.history IS 'История исполненных сигналов';
COMMENT ON TABLE signals.metrics IS 'Метрики производительности сигналов';

-- Комментарии к колонкам
COMMENT ON COLUMN signals.candidates.confidence IS 'Уверенность в сигнале (0-1)';
COMMENT ON COLUMN signals.candidates.expected_r IS 'Ожидаемая доходность после комиссий';
COMMENT ON COLUMN signals.candidates.rationale IS 'Обоснование торгового решения';
COMMENT ON COLUMN signals.live.expires_at IS 'Время истечения сигнала';
COMMENT ON COLUMN signals.history.actual_r IS 'Фактическая доходность';
COMMENT ON COLUMN signals.history.performance_metrics IS 'Метрики производительности';
