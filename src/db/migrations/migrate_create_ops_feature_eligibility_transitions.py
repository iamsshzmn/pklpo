from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

FEATURE_ELIGIBILITY_TRANSITIONS_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
    CREATE TABLE IF NOT EXISTS ops.feature_eligibility_transitions (
    id                BIGSERIAL PRIMARY KEY,
    symbol            TEXT        NOT NULL,
    timeframe         TEXT        NOT NULL,
    from_state        TEXT,
    to_state          TEXT        NOT NULL,
    actual_bars       BIGINT,
    reason_flags      TEXT[]      NOT NULL DEFAULT '{}',
    evaluator_run_id  TEXT,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now()
)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_fet_occurred
    ON ops.feature_eligibility_transitions (occurred_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_fet_symbol
    ON ops.feature_eligibility_transitions (
        symbol,
        timeframe,
        occurred_at DESC
    )
    """,
)

FEATURE_ELIGIBILITY_TRANSITIONS_SQL = (
    ";\n\n".join(FEATURE_ELIGIBILITY_TRANSITIONS_STATEMENTS) + ";"
)


async def migrate_create_ops_feature_eligibility_transitions() -> None:
    """Create append-only feature eligibility transition audit table.

    Rollback:
        DROP TABLE IF EXISTS ops.feature_eligibility_transitions;
    """
    async with get_db_session() as session:
        try:
            for statement in FEATURE_ELIGIBILITY_TRANSITIONS_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("ops.feature_eligibility_transitions table ensured")
        except Exception:
            await session.rollback()
            raise
