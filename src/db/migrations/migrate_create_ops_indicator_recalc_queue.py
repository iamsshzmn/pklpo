from __future__ import annotations

import logging

from sqlalchemy import text

from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)

INDICATOR_RECALC_QUEUE_STATUSES = (
    "queued",
    "claimed",
    "completed",
    "blocked",
    "failed",
)

INDICATOR_RECALC_QUEUE_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS ops",
    """
    CREATE TABLE IF NOT EXISTS ops.indicator_recalc_queue (
    id             BIGSERIAL PRIMARY KEY,
    symbol         TEXT        NOT NULL,
    timeframe      TEXT        NOT NULL,
    range_start_ts BIGINT      NOT NULL,
    range_end_ts   BIGINT      NOT NULL,
    warmup_bars    INTEGER     NOT NULL DEFAULT 500,
    status         TEXT        NOT NULL DEFAULT 'queued',
    enqueued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    source_dag     TEXT,
    detail         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT chk_irq_status CHECK (status IN (
        'queued','claimed','completed','blocked','failed'
    )),
    CONSTRAINT chk_irq_range CHECK (range_start_ts < range_end_ts),
    CONSTRAINT uq_irq_symbol_tf_range UNIQUE (
        symbol,
        timeframe,
        range_start_ts,
        range_end_ts
    )
)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_irq_claim
    ON ops.indicator_recalc_queue (status, enqueued_at, id)
    WHERE status IN ('queued', 'blocked')
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_irq_symbol_tf
    ON ops.indicator_recalc_queue (symbol, timeframe, enqueued_at DESC)
    """,
)

INDICATOR_RECALC_QUEUE_SQL = ";\n\n".join(INDICATOR_RECALC_QUEUE_STATEMENTS) + ";"


async def migrate_create_ops_indicator_recalc_queue() -> None:
    """Create durable indicator recalculation queue.

    Rollback:
        DROP TABLE IF EXISTS ops.indicator_recalc_queue;
    """
    async with get_db_session() as session:
        try:
            for statement in INDICATOR_RECALC_QUEUE_STATEMENTS:
                await session.execute(text(statement))
            await session.commit()
            logger.info("ops.indicator_recalc_queue table ensured")
        except Exception:
            await session.rollback()
            raise
