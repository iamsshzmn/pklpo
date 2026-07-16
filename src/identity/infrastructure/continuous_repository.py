"""SQL publisher for continuous OHLCV snapshots."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from src.identity.application.build_job import derive_identity_snapshot
from src.identity.application.continuous_build_job import (
    ContinuousBuildContext,
    ContinuousSnapshot,
    RawOhlcvBar,
    timeframe_duration_ms,
)
from src.identity.infrastructure.repository import SqlIdentityBuildRepository
from src.utils.session_utils import get_db_session

if TYPE_CHECKING:
    from src.identity.domain import IdentitySnapshot, SeriesMemberRow

LOAD_RAW_BARS_SQL = """
SELECT
    symbol AS source_symbol,
    timeframe,
    timestamp,
    open,
    high,
    low,
    close,
    volume
FROM public.swap_ohlcv_p
WHERE symbol = :source_symbol
  AND timeframe = :timeframe
  AND timestamp >= CAST(:load_start AS bigint)
  AND (CAST(:valid_to AS bigint) IS NULL OR timestamp < CAST(:valid_to AS bigint))
ORDER BY timestamp
""".strip()

PUBLISH_DELETE_SQL = (
    """
DELETE FROM core.continuous_ohlcv_p
WHERE series_id = ANY(:series_ids)
    """.strip(),
    """
DELETE FROM core.series_segments
WHERE series_id = ANY(:series_ids)
    """.strip(),
)

INSERT_CONTINUOUS_ROWS_SQL = """
INSERT INTO core.continuous_ohlcv_p (
    series_id, timeframe, timestamp, open, high, low, close, volume,
    source_venue, source_symbol, source_timestamp, segment_id, succession_id,
    adjustment_factor, bar_kind, data_status, run_id, algo_version, params_hash,
    snapshot_id
) VALUES (
    :series_id, :timeframe, :timestamp, :open, :high, :low, :close, :volume,
    :source_venue, :source_symbol, :source_timestamp, :segment_id, :succession_id,
    :adjustment_factor, :bar_kind, :data_status, :run_id, :algo_version,
    :params_hash, :snapshot_id
)
ON CONFLICT (series_id, timeframe, timestamp) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    source_venue = EXCLUDED.source_venue,
    source_symbol = EXCLUDED.source_symbol,
    source_timestamp = EXCLUDED.source_timestamp,
    segment_id = EXCLUDED.segment_id,
    succession_id = EXCLUDED.succession_id,
    adjustment_factor = EXCLUDED.adjustment_factor,
    bar_kind = EXCLUDED.bar_kind,
    data_status = EXCLUDED.data_status,
    run_id = EXCLUDED.run_id,
    algo_version = EXCLUDED.algo_version,
    params_hash = EXCLUDED.params_hash,
    snapshot_id = EXCLUDED.snapshot_id
""".strip()

INSERT_SEGMENTS_SQL = """
INSERT INTO core.series_segments (
    series_id, timeframe, segment_id, source_venue, source_symbol,
    segment_start_ts, segment_end_ts, segment_order, reset_features_from_here,
    known_from
) VALUES (
    :series_id, :timeframe, :segment_id, :source_venue, :source_symbol,
    :segment_start_ts, :segment_end_ts, :segment_order, :reset_features_from_here,
    now()
)
ON CONFLICT (series_id, timeframe, segment_id, known_from) DO UPDATE SET
    source_venue = EXCLUDED.source_venue,
    source_symbol = EXCLUDED.source_symbol,
    segment_start_ts = EXCLUDED.segment_start_ts,
    segment_end_ts = EXCLUDED.segment_end_ts,
    segment_order = EXCLUDED.segment_order,
    reset_features_from_here = EXCLUDED.reset_features_from_here
""".strip()

INSERT_CONTINUOUS_AUDIT_SQL = """
INSERT INTO ops.continuous_ohlcv_build_audit (
    run_id, series_id, timeframe, algo_version, params_hash, snapshot_id,
    started_at, finished_at, status, row_count, gap_count, segment_count
) VALUES (
    :run_id, :series_id, :timeframe, :algo_version, :params_hash, :snapshot_id,
    now(), now(), 'success', :row_count, :gap_count, :segment_count
)
ON CONFLICT (run_id) DO UPDATE SET
    finished_at = EXCLUDED.finished_at,
    status = EXCLUDED.status,
    row_count = EXCLUDED.row_count,
    gap_count = EXCLUDED.gap_count,
    segment_count = EXCLUDED.segment_count,
    updated_at = now()
""".strip()

INSERT_CONTINUOUS_FAILURE_AUDIT_SQL = """
INSERT INTO ops.continuous_ohlcv_build_audit (
    run_id, series_id, timeframe, algo_version, params_hash, snapshot_id,
    started_at, finished_at, status, error_type, error_message_hash
) VALUES (
    :run_id, :series_id, :timeframe, :algo_version, :params_hash, :snapshot_id,
    now(), now(), 'failed', :error_type, :error_message_hash
)
ON CONFLICT (run_id) DO UPDATE SET
    finished_at = EXCLUDED.finished_at,
    status = EXCLUDED.status,
    error_type = EXCLUDED.error_type,
    error_message_hash = EXCLUDED.error_message_hash,
    updated_at = now()
""".strip()


class SqlContinuousBuildRepository:
    """Persist continuous rows, segments, and audit as one transaction."""

    async def publish_snapshot(
        self,
        snapshot: ContinuousSnapshot,
        context: ContinuousBuildContext,
        *,
        gap_count: int = 0,
    ) -> None:
        series_ids = sorted(
            {row.series_id for row in snapshot.rows}
            | {segment.series_id for segment in snapshot.segments}
        )
        if not series_ids:
            return

        async with get_db_session() as session:
            try:
                for statement in PUBLISH_DELETE_SQL:
                    await session.execute(text(statement), {"series_ids": series_ids})
                for segment in snapshot.segments:
                    await session.execute(text(INSERT_SEGMENTS_SQL), segment.__dict__)
                for row in snapshot.rows:
                    await session.execute(
                        text(INSERT_CONTINUOUS_ROWS_SQL), row.__dict__
                    )
                await session.execute(
                    text(INSERT_CONTINUOUS_AUDIT_SQL),
                    {
                        "run_id": context.run_id,
                        "series_id": ",".join(series_ids),
                        "timeframe": None,
                        "algo_version": context.algo_version,
                        "params_hash": context.params_hash,
                        "snapshot_id": context.snapshot_id,
                        "row_count": len(snapshot.rows),
                        "gap_count": gap_count,
                        "segment_count": len(snapshot.segments),
                    },
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def record_failure(
        self,
        context: ContinuousBuildContext,
        error_type: str,
        error_hash: str,
        *,
        series_id: str = "*",
        timeframe: str | None = None,
    ) -> None:
        """Persist a failed continuous-build audit row (§17.4 'continuous
        build' row's audit column). `series_id` defaults to the wildcard
        sentinel `"*"` because a failure can happen before any composite
        series_ids are even known (e.g. `load_snapshot` itself failing) —
        never omitted or left NULL, since the table's `series_id` column is
        NOT NULL."""
        async with get_db_session() as session:
            try:
                await session.execute(
                    text(INSERT_CONTINUOUS_FAILURE_AUDIT_SQL),
                    {
                        "run_id": context.run_id,
                        "series_id": series_id,
                        "timeframe": timeframe,
                        "algo_version": context.algo_version,
                        "params_hash": context.params_hash,
                        "snapshot_id": context.snapshot_id,
                        "error_type": error_type,
                        "error_message_hash": error_hash,
                    },
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise


class SqlContinuousIdentityRepository:
    """Load and derive the PIT identity snapshot for continuous materialization."""

    def __init__(self, identity_repository: SqlIdentityBuildRepository | None = None):
        self._identity_repository = identity_repository or SqlIdentityBuildRepository()

    async def load_snapshot(self, as_of) -> IdentitySnapshot:
        inputs = await self._identity_repository.load_inputs(as_of)
        return derive_identity_snapshot(inputs, as_of=as_of)


class SqlContinuousRawRepository:
    """Load raw OHLCV rows for composite series members."""

    def __init__(self, *, timeframes: list[str] | None = None) -> None:
        self._timeframes = timeframes or [
            "1m",
            "5m",
            "15m",
            "30m",
            "1H",
            "4H",
            "12H",
            "1D",
            "1W",
            "1M",
        ]

    async def load_bars(self, members: list[SeriesMemberRow]) -> list[RawOhlcvBar]:
        bars: list[RawOhlcvBar] = []
        async with get_db_session() as session:
            for member in members:
                for timeframe in self._timeframes:
                    rows = (
                        await session.execute(
                            text(LOAD_RAW_BARS_SQL),
                            {
                                "source_symbol": member.source_symbol,
                                "timeframe": timeframe,
                                "load_start": max(
                                    0,
                                    member.valid_from
                                    - timeframe_duration_ms(timeframe)
                                    + 1,
                                ),
                                "valid_to": member.valid_to,
                            },
                        )
                    ).fetchall()
                    bars.extend(
                        RawOhlcvBar(
                            source_venue=member.source_venue,
                            source_symbol=str(row[0]),
                            timeframe=str(row[1]),
                            timestamp=int(row[2]),
                            open=row[3],
                            high=row[4],
                            low=row[5],
                            close=row[6],
                            volume=row[7],
                        )
                        for row in rows
                    )
        return bars
