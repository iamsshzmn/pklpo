"""Migration 450: create ops.pipeline_recovery_decisions table."""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

PIPELINE_RECOVERY_DECISIONS_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
    CREATE TABLE IF NOT EXISTS ops.pipeline_recovery_decisions (
        id                   BIGSERIAL    PRIMARY KEY,
        created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
        controller_dag_id    TEXT         NOT NULL,
        controller_dag_run_id TEXT        NULL,
        logical_date         TIMESTAMPTZ  NULL,
        decision_status      TEXT         NOT NULL,
        action_kind          TEXT         NOT NULL,
        target_dag_id        TEXT         NULL,
        target_run_id        TEXT         NULL,
        reason               TEXT         NOT NULL,
        symbol               TEXT         NULL,
        timeframe            TEXT         NULL,
        priority             INTEGER      NOT NULL DEFAULT 0,
        cooldown_until       TIMESTAMPTZ  NULL,
        precheck_payload     JSONB        NOT NULL DEFAULT '{}'::jsonb,
        trigger_conf         JSONB        NOT NULL DEFAULT '{}'::jsonb,
        safety_payload       JSONB        NOT NULL DEFAULT '{}'::jsonb,
        error                TEXT         NULL,
        CONSTRAINT chk_pipeline_recovery_decision_status CHECK (
            decision_status IN (
                'skip', 'precheck_failed', 'candidate', 'triggered', 'trigger_failed'
            )
        ),
        CONSTRAINT chk_pipeline_recovery_action_kind CHECK (
            action_kind IN ('none', 'repair', 'bootstrap')
        )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_pipeline_recovery_decisions_created_at
    ON ops.pipeline_recovery_decisions (created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_pipeline_recovery_decisions_cooldown
    ON ops.pipeline_recovery_decisions (
        action_kind, target_dag_id, symbol, timeframe, created_at DESC
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_pipeline_recovery_decisions_target_run
    ON ops.pipeline_recovery_decisions (target_dag_id, target_run_id)
    """,
)


async def migrate_create_ops_pipeline_recovery_decisions() -> None:
    """Create ops.pipeline_recovery_decisions table for controller audit and cooldown.

    Rollback:
        DROP TABLE IF EXISTS ops.pipeline_recovery_decisions;
    """
    async with get_db_session() as session:
        try:
            for statement in PIPELINE_RECOVERY_DECISIONS_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("ops.pipeline_recovery_decisions table ensured")
        except Exception:
            await session.rollback()
            raise
