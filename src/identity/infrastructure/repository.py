"""SQL repository for identity build inputs and publication."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import text

from src.identity.domain import (
    ApprovedGapClassification,
    ApprovedSuccession,
    IdentityBuildContext,
    IdentityBuildInputs,
    IdentitySnapshot,
    RawInstrument,
)
from src.utils.session_utils import get_db_session

if TYPE_CHECKING:
    from datetime import datetime

LOAD_INSTRUMENTS_SQL = """
SELECT symbol, COALESCE(inst_type, 'SWAP') AS inst_type, list_time
FROM public.instruments
WHERE symbol IS NOT NULL
ORDER BY symbol
""".strip()

LOAD_SUCCESSIONS_SQL = """
SELECT old_symbol, new_symbol, venue, inst_type, ratio, old_stop_ts, new_start_ts,
       effective_from, known_from, approved_at
FROM ops.symbol_succession
WHERE status = 'approved'
  AND known_from <= :as_of
  AND approved_at <= :as_of
ORDER BY old_symbol, new_symbol, known_from
""".strip()

LOAD_GAP_CLASSIFICATIONS_SQL = """
SELECT series_id, COALESCE(timeframe, '*') AS timeframe, range_start_ts, range_end_ts,
       gap_type, recoverability, evidence, known_from, approved_at
FROM ops.gap_classification
WHERE status = 'approved'
  AND known_from <= :as_of
  AND approved_at <= :as_of
ORDER BY series_id, timeframe, range_start_ts
""".strip()

PUBLISH_DELETE_SQL = (
    "DELETE FROM core.series_gap_ranges",
    "DELETE FROM core.series_segments",
    "DELETE FROM core.series_alias",
    "DELETE FROM core.series_members",
    "DELETE FROM core.series_registry",
)

PUBLISH_INSERT_SQL = (
    """
INSERT INTO core.series_registry (
    series_id, series_label, asset_id, series_kind, status,
    kind_current_since, status_current_since
) VALUES (
    :series_id, :series_label, :asset_id, :series_kind, :status,
    :known_from, :known_from
)
    """.strip(),
    """
INSERT INTO core.series_members (
    series_id, source_venue, source_symbol, valid_from, valid_to,
    known_from, adjustment_factor, succession_id
) VALUES (
    :series_id, :source_venue, :source_symbol, :valid_from, :valid_to,
    :known_from, :adjustment_factor, :succession_id
)
    """.strip(),
    """
INSERT INTO core.series_alias (
    old_series_id, canonical_series_id, known_from, reason
) VALUES (
    :old_series_id, :canonical_series_id, :known_from, :reason
)
    """.strip(),
    """
INSERT INTO core.series_gap_ranges (
    series_id, timeframe, gap_start_ts, gap_end_ts, gap_type,
    recoverability, reason, known_from
) VALUES (
    :series_id, :timeframe, :gap_start_ts, :gap_end_ts, :gap_type,
    :recoverability, :reason, :known_from
)
    """.strip(),
)

INSERT_AUDIT_SQL = """
INSERT INTO ops.series_identity_build_audit (
    run_id, algo_version, params_hash, snapshot_id, started_at, finished_at,
    status, input_hash, rows_inserted, rows_deleted, gap_count, segment_count
) VALUES (
    :run_id, :algo_version, :params_hash, :snapshot_id, :started_at, now(),
    'success', :input_hash, :rows_inserted, :rows_deleted, :gap_count, :segment_count
)
ON CONFLICT (run_id) DO UPDATE SET
    finished_at = EXCLUDED.finished_at,
    status = EXCLUDED.status,
    rows_inserted = EXCLUDED.rows_inserted,
    rows_deleted = EXCLUDED.rows_deleted,
    gap_count = EXCLUDED.gap_count,
    segment_count = EXCLUDED.segment_count
""".strip()

INSERT_RECALC_QUEUE_SQL = """
INSERT INTO ops.indicator_recalc_queue (
    symbol, timeframe, range_start_ts, range_end_ts, source_dag, detail
) VALUES (
    :series_id, '*', 0, 9223372036854775807, 'identity_build',
    CAST(:detail AS jsonb)
)
ON CONFLICT (symbol, timeframe, range_start_ts, range_end_ts) DO NOTHING
""".strip()

INSERT_FAILURE_AUDIT_SQL = """
INSERT INTO ops.series_identity_build_audit (
    run_id, algo_version, params_hash, snapshot_id, started_at, finished_at,
    status, input_hash, error_type, error_message_hash
) VALUES (
    :run_id, :algo_version, :params_hash, :snapshot_id, :started_at, now(),
    'failed', :input_hash, :error_type, :error_message_hash
)
ON CONFLICT (run_id) DO UPDATE SET
    finished_at = EXCLUDED.finished_at,
    status = EXCLUDED.status,
    error_type = EXCLUDED.error_type,
    error_message_hash = EXCLUDED.error_message_hash
""".strip()


def _timestamp_to_ms(value: datetime | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(value.timestamp() * 1000)


class SqlIdentityBuildRepository:
    """SQL adapter for identity build inputs and atomic snapshot publication."""

    async def load_inputs(self, as_of: datetime) -> IdentityBuildInputs:
        async with get_db_session() as session:
            instrument_rows = (
                await session.execute(text(LOAD_INSTRUMENTS_SQL))
            ).fetchall()
            succession_rows = (
                await session.execute(text(LOAD_SUCCESSIONS_SQL), {"as_of": as_of})
            ).fetchall()
            gap_rows = (
                await session.execute(
                    text(LOAD_GAP_CLASSIFICATIONS_SQL), {"as_of": as_of}
                )
            ).fetchall()

        return IdentityBuildInputs(
            instruments=[
                RawInstrument(
                    symbol=str(row[0]),
                    venue="OKX",
                    inst_type=str(row[1] or "SWAP"),
                    list_time=row[2],
                )
                for row in instrument_rows
            ],
            successions=[
                ApprovedSuccession(
                    old_symbol=str(row[0]),
                    new_symbol=str(row[1]),
                    venue=str(row[2]),
                    inst_type=str(row[3]),
                    ratio=Decimal(str(row[4])),
                    old_stop_ts=_timestamp_to_ms(row[5]),
                    new_start_ts=_timestamp_to_ms(row[6]),
                    effective_from=row[7],
                    known_from=row[8],
                    approved_at=row[9],
                )
                for row in succession_rows
            ],
            gap_classifications=[
                ApprovedGapClassification(
                    series_id=str(row[0]),
                    timeframe=str(row[1]),
                    range_start_ts=int(row[2]),
                    range_end_ts=int(row[3]),
                    gap_type=str(row[4]),
                    recoverability=str(row[5]),
                    reason=json.dumps(row[6], sort_keys=True, default=str),
                    known_from=row[7],
                    approved_at=row[8],
                )
                for row in gap_rows
            ],
        )

    async def publish_snapshot(
        self, snapshot: IdentitySnapshot, context: IdentityBuildContext
    ) -> None:
        async with get_db_session() as session:
            try:
                for statement in PUBLISH_DELETE_SQL:
                    await session.execute(text(statement))

                for row in snapshot.registry:
                    await session.execute(
                        text(PUBLISH_INSERT_SQL[0]),
                        {
                            "series_id": row.series_id,
                            "series_label": row.series_label,
                            "asset_id": row.asset_id,
                            "series_kind": row.series_kind,
                            "status": row.status,
                            "known_from": row.known_from,
                        },
                    )

                for row in snapshot.members:
                    await session.execute(
                        text(PUBLISH_INSERT_SQL[1]),
                        {
                            "series_id": row.series_id,
                            "source_venue": row.source_venue,
                            "source_symbol": row.source_symbol,
                            "valid_from": row.valid_from,
                            "valid_to": row.valid_to,
                            "known_from": row.known_from,
                            "adjustment_factor": row.adjustment_factor,
                            "succession_id": row.succession_id,
                        },
                    )

                for row in snapshot.aliases:
                    await session.execute(
                        text(PUBLISH_INSERT_SQL[2]),
                        {
                            "old_series_id": row.old_series_id,
                            "canonical_series_id": row.canonical_series_id,
                            "known_from": row.known_from,
                            "reason": row.reason,
                        },
                    )

                for row in snapshot.gap_ranges:
                    await session.execute(
                        text(PUBLISH_INSERT_SQL[3]),
                        {
                            "series_id": row.series_id,
                            "timeframe": row.timeframe,
                            "gap_start_ts": row.gap_start_ts,
                            "gap_end_ts": row.gap_end_ts,
                            "gap_type": row.gap_type,
                            "recoverability": row.recoverability,
                            "reason": row.reason,
                            "known_from": row.known_from,
                        },
                    )

                rows_inserted = (
                    len(snapshot.registry)
                    + len(snapshot.members)
                    + len(snapshot.aliases)
                    + len(snapshot.gap_ranges)
                )
                await session.execute(
                    text(INSERT_AUDIT_SQL),
                    {
                        "run_id": context.run_id,
                        "algo_version": context.algo_version,
                        "params_hash": context.params_hash,
                        "snapshot_id": None,
                        "started_at": context.as_of,
                        "input_hash": context.params_hash,
                        "rows_inserted": rows_inserted,
                        "rows_deleted": 0,
                        "gap_count": len(snapshot.gap_ranges),
                        "segment_count": 0,
                    },
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def enqueue_recalc(
        self, series_ids: list[str], context: IdentityBuildContext
    ) -> None:
        async with get_db_session() as session:
            try:
                for series_id in series_ids:
                    await session.execute(
                        text(INSERT_RECALC_QUEUE_SQL),
                        {
                            "series_id": series_id,
                            "detail": json.dumps(
                                {
                                    "run_id": context.run_id,
                                    "reason": "identity_build",
                                },
                                sort_keys=True,
                            ),
                        },
                    )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def record_failure(
        self, context: IdentityBuildContext, error_type: str, error_hash: str
    ) -> None:
        async with get_db_session() as session:
            try:
                await session.execute(
                    text(INSERT_FAILURE_AUDIT_SQL),
                    {
                        "run_id": context.run_id,
                        "algo_version": context.algo_version,
                        "params_hash": context.params_hash,
                        "snapshot_id": None,
                        "started_at": context.as_of,
                        "input_hash": context.params_hash,
                        "error_type": error_type,
                        "error_message_hash": error_hash,
                    },
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise
