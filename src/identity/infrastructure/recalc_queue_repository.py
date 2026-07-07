"""SQL adapter for precisely-bounded indicator recalc enqueueing (§15.5).

Reuses the existing `ops.indicator_recalc_queue` table (see
`src.db.migrations.migrate_create_ops_indicator_recalc_queue`) — the same
table the identity build job already writes to via
`src.identity.infrastructure.repository.INSERT_RECALC_QUEUE_SQL`. That job
enqueues a blanket `0..MAX_BIGINT` range per series (a full-series recalc,
appropriate right after a build). This adapter instead enqueues the narrow,
`compute_affected_recalc_range`-bounded range for a single series/timeframe,
for the feature-cutover path (Task 5.3).
"""

from __future__ import annotations

import json

from sqlalchemy import text

from src.utils.session_utils import get_db_session

ENQUEUE_PRECISE_RECALC_SQL = """
INSERT INTO ops.indicator_recalc_queue (
    symbol, timeframe, range_start_ts, range_end_ts, source_dag, detail
) VALUES (
    :series_id, :timeframe, :range_start_ts, :range_end_ts, :source_dag,
    CAST(:detail AS jsonb)
)
ON CONFLICT (symbol, timeframe, range_start_ts, range_end_ts) DO NOTHING
""".strip()


class SqlRecalcQueueRepository:
    """SQL adapter implementing
    `src.identity.application.feature_cutover.RecalcQueueRepository`."""

    async def enqueue(
        self,
        *,
        series_id: str,
        timeframe: str,
        range_start_ts: int,
        range_end_ts: int,
        source_dag: str = "feature_cutover_ton_gram",
        detail: dict[str, object] | None = None,
    ) -> None:
        async with get_db_session() as session:
            try:
                await session.execute(
                    text(ENQUEUE_PRECISE_RECALC_SQL),
                    {
                        "series_id": series_id,
                        "timeframe": timeframe,
                        "range_start_ts": range_start_ts,
                        "range_end_ts": range_end_ts,
                        "source_dag": source_dag,
                        "detail": json.dumps(detail or {}, sort_keys=True, default=str),
                    },
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
