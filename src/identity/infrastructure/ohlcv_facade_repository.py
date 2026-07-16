"""SQL repository for the identity-aware OHLCV read facade."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import text

from src.utils.session_utils import get_db_session

if TYPE_CHECKING:
    from collections.abc import Mapping

RESOLVE_ALIAS_SQL = """
SELECT canonical_series_id
FROM core.series_alias
WHERE old_series_id = :series_id
  AND known_from <= :as_of
  AND (known_to IS NULL OR known_to > :as_of)
ORDER BY known_from DESC
LIMIT 1
""".strip()

GET_SERIES_KIND_SQL = """
SELECT series_kind
FROM core.series_registry
WHERE series_id = :series_id
LIMIT 1
""".strip()

READ_RAW_SQL = """
SELECT
    symbol AS series_id,
    timeframe,
    timestamp,
    open,
    high,
    low,
    close,
    volume,
    ('raw:' || symbol || ':' || timeframe) AS segment_id,
    'OKX' AS source_venue,
    symbol AS source_symbol,
    timestamp AS source_timestamp,
    'native' AS bar_kind,
    'complete' AS data_status,
    CAST(NULL AS text) AS succession_id,
    CAST(1 AS numeric) AS adjustment_factor,
    false AS is_gap,
    CAST(NULL AS text) AS gap_type
FROM public.swap_ohlcv_p
WHERE symbol = :series_id
  AND timeframe = :timeframe
  AND timestamp >= CAST(:start_ts AS bigint)
  AND timestamp < CAST(:end_ts AS bigint)
ORDER BY timestamp
""".strip()

READ_CONTINUOUS_SQL = """
SELECT
    series_id,
    timeframe,
    timestamp,
    open,
    high,
    low,
    close,
    volume,
    segment_id,
    source_venue,
    source_symbol,
    source_timestamp,
    bar_kind,
    data_status,
    succession_id,
    adjustment_factor,
    false AS is_gap,
    CAST(NULL AS text) AS gap_type
FROM core.continuous_ohlcv_p
WHERE series_id = :series_id
  AND timeframe = :timeframe
  AND timestamp >= CAST(:start_ts AS bigint)
  AND timestamp < CAST(:end_ts AS bigint)
ORDER BY timestamp
""".strip()

READ_GAP_MARKERS_SQL = """
SELECT
    series_id,
    :timeframe AS timeframe,
    GREATEST(gap_start_ts, CAST(:start_ts AS bigint)) AS timestamp,
    gap_type,
    ('gap:' || series_id || ':' || :timeframe || ':' || gap_start_ts) AS segment_id
FROM core.series_gap_ranges
WHERE series_id = :series_id
  AND (timeframe = :timeframe OR timeframe = '*')
  AND gap_start_ts < CAST(:end_ts AS bigint)
  AND gap_end_ts > CAST(:start_ts AS bigint)
  AND known_from <= :as_of
  AND (known_to IS NULL OR known_to > :as_of)
ORDER BY timestamp
""".strip()

GET_ADJUSTMENT_FACTOR_SQL = """
SELECT adjustment_factor
FROM core.series_adjustments
WHERE series_id = :series_id
  AND effective_ts <= CAST(:timestamp AS bigint)
  AND known_from <= :as_of
  AND (known_to IS NULL OR known_to > :as_of)
ORDER BY effective_ts DESC, known_from DESC
LIMIT 1
""".strip()


class SqlOhlcvFacadeRepository:
    async def resolve_alias(self, series_id: str, as_of: datetime | None) -> str:
        async with get_db_session() as session:
            result = await session.execute(
                text(RESOLVE_ALIAS_SQL),
                {"series_id": series_id, "as_of": _as_of(as_of)},
            )
            resolved = result.scalar_one_or_none()
        return str(resolved) if resolved is not None else series_id

    async def get_series_kind(self, series_id: str, as_of: datetime | None) -> str:
        async with get_db_session() as session:
            result = await session.execute(
                text(GET_SERIES_KIND_SQL), {"series_id": series_id}
            )
            series_kind = result.scalar_one_or_none()
        return str(series_kind) if series_kind is not None else "trivial"

    async def read_raw(
        self, series_id: str, timeframe: str, start_ts: int, end_ts: int
    ) -> list[Mapping[str, object]]:
        return await _fetch_mappings(
            READ_RAW_SQL,
            {
                "series_id": series_id,
                "timeframe": timeframe,
                "start_ts": start_ts,
                "end_ts": end_ts,
            },
        )

    async def read_continuous(
        self, series_id: str, timeframe: str, start_ts: int, end_ts: int
    ) -> list[Mapping[str, object]]:
        return await _fetch_mappings(
            READ_CONTINUOUS_SQL,
            {
                "series_id": series_id,
                "timeframe": timeframe,
                "start_ts": start_ts,
                "end_ts": end_ts,
            },
        )

    async def read_gap_markers(
        self,
        series_id: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        as_of: datetime | None,
    ) -> list[Mapping[str, object]]:
        return await _fetch_mappings(
            READ_GAP_MARKERS_SQL,
            {
                "series_id": series_id,
                "timeframe": timeframe,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "as_of": _as_of(as_of),
            },
        )

    async def get_adjustment_factor(
        self, series_id: str, timestamp: int, as_of: datetime | None
    ) -> Decimal:
        async with get_db_session() as session:
            result = await session.execute(
                text(GET_ADJUSTMENT_FACTOR_SQL),
                {
                    "series_id": series_id,
                    "timestamp": timestamp,
                    "as_of": _as_of(as_of),
                },
            )
            factor = result.scalar_one_or_none()
        return Decimal(str(factor)) if factor is not None else Decimal("1")


async def _fetch_mappings(
    statement: str, params: Mapping[str, object]
) -> list[Mapping[str, object]]:
    async with get_db_session() as session:
        result = await session.execute(text(statement), params)
        return [dict(row) for row in result.mappings().all()]


def _as_of(value: datetime | None) -> datetime:
    return value if value is not None else datetime.now(tz=UTC)
