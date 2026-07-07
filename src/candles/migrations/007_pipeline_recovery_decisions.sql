-- Миграция 007: Таблица решений контроллера восстановления пайплайна
-- Дата: 2026-06-20
-- Описание: Создание ops.pipeline_recovery_decisions для аудита и cooldown-логики
--           контроллера pipeline_recovery_controller.

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.pipeline_recovery_decisions (
    id                      BIGSERIAL       PRIMARY KEY,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Контекст запуска контроллера
    controller_dag_id       TEXT            NOT NULL,
    controller_dag_run_id   TEXT,
    logical_date            TIMESTAMPTZ,

    -- Решение
    decision_status         TEXT            NOT NULL,  -- skip | precheck_failed | candidate | triggered | trigger_failed
    action_kind             TEXT            NOT NULL,  -- none | repair | bootstrap
    target_dag_id           TEXT,
    target_run_id           TEXT,
    reason                  TEXT            NOT NULL,

    -- Инструмент
    symbol                  TEXT,
    timeframe               TEXT,
    priority                INTEGER         NOT NULL DEFAULT 0,
    cooldown_until          TIMESTAMPTZ,

    -- Полезная нагрузка
    precheck_payload        JSONB           NOT NULL DEFAULT '{}',
    trigger_conf            JSONB           NOT NULL DEFAULT '{}',
    safety_payload          JSONB           NOT NULL DEFAULT '{}',
    error                   TEXT
);

-- Индекс для cooldown-запросов (GET по ключу action+dag+symbol+tf за окно времени)
CREATE INDEX IF NOT EXISTS idx_prd_cooldown
    ON ops.pipeline_recovery_decisions (action_kind, target_dag_id, symbol, timeframe, created_at DESC);

-- Индекс для аудитных запросов по контроллеру
CREATE INDEX IF NOT EXISTS idx_prd_controller_dag
    ON ops.pipeline_recovery_decisions (controller_dag_id, created_at DESC);

-- Индекс для фильтрации по статусу
CREATE INDEX IF NOT EXISTS idx_prd_decision_status
    ON ops.pipeline_recovery_decisions (decision_status, created_at DESC);

COMMENT ON TABLE ops.pipeline_recovery_decisions IS
    'Аудит и cooldown-хранилище для pipeline_recovery_controller. '
    'Каждая запись — одно решение контроллера по (symbol, timeframe).';

COMMENT ON COLUMN ops.pipeline_recovery_decisions.decision_status IS
    'skip | precheck_failed | candidate | triggered | trigger_failed';
COMMENT ON COLUMN ops.pipeline_recovery_decisions.action_kind IS
    'none | repair | bootstrap';
COMMENT ON COLUMN ops.pipeline_recovery_decisions.cooldown_until IS
    'Timestamp до которого повторный триггер для этого ключа заблокирован';
