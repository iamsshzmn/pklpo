from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

FEATURE_ELIGIBILITY_STATES = (
    "eligible",
    "insufficient_history",
    "incomplete_history",
    "invalid_history",
    "informational_only",
    "disabled",
)

FEATURE_ELIGIBILITY_TABLE_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
    CREATE TABLE IF NOT EXISTS ops.feature_eligibility (
    symbol               TEXT        NOT NULL,
    timeframe            TEXT        NOT NULL,
    state                TEXT        NOT NULL,
    required_bars        INTEGER     NOT NULL,
    actual_bars          BIGINT      NOT NULL DEFAULT 0,
    coverage_pct         NUMERIC(5,2),
    first_ts             BIGINT,
    last_ts              BIGINT,
    reason_flags         TEXT[]      NOT NULL DEFAULT '{}',
    can_compute_features BOOLEAN     NOT NULL DEFAULT FALSE,
    can_score            BOOLEAN     NOT NULL DEFAULT FALSE,
    can_train_ml         BOOLEAN     NOT NULL DEFAULT FALSE,
    context_only         BOOLEAN     NOT NULL DEFAULT FALSE,
    detail               JSONB       NOT NULL DEFAULT '{}'::jsonb,
    previous_state       TEXT,
    state_changed_at     TIMESTAMPTZ,
    evaluated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    evaluator_run_id     TEXT,
    PRIMARY KEY (symbol, timeframe),
    CONSTRAINT chk_fe_state CHECK (state IN (
        'eligible','insufficient_history','incomplete_history',
        'invalid_history','informational_only','disabled'
    ))
)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_fe_state
    ON ops.feature_eligibility (timeframe, state)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_fe_evaluated
    ON ops.feature_eligibility (evaluated_at DESC)
    """,
)

FEATURE_ELIGIBILITY_TABLE_SQL = ";\n\n".join(FEATURE_ELIGIBILITY_TABLE_STATEMENTS) + ";"


async def migrate_create_ops_feature_eligibility() -> None:
    """Create materialized per-symbol feature eligibility state.

    Rollback:
        DROP TABLE IF EXISTS ops.feature_eligibility;
    """
    async with get_db_session() as session:
        try:
            for statement in FEATURE_ELIGIBILITY_TABLE_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("ops.feature_eligibility table ensured")
        except Exception:
            await session.rollback()
            raise
