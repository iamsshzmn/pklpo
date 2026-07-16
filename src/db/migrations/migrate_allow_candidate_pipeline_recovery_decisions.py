"""Migration 460: allow candidate recovery decisions."""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

ALLOW_CANDIDATE_PIPELINE_RECOVERY_DECISIONS_STATEMENTS = (
    """
    ALTER TABLE ops.pipeline_recovery_decisions
    DROP CONSTRAINT IF EXISTS chk_pipeline_recovery_decision_status
    """,
    """
    ALTER TABLE ops.pipeline_recovery_decisions
    ADD CONSTRAINT chk_pipeline_recovery_decision_status CHECK (
        decision_status IN (
            'skip', 'precheck_failed', 'candidate', 'triggered', 'trigger_failed'
        )
    )
    """,
)


async def migrate_allow_candidate_pipeline_recovery_decisions() -> None:
    """Allow candidate as an eligible-but-not-triggered controller decision state."""
    async with get_db_session() as session:
        try:
            for statement in ALLOW_CANDIDATE_PIPELINE_RECOVERY_DECISIONS_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("ops.pipeline_recovery_decisions candidate status allowed")
        except Exception:
            await session.rollback()
            raise
