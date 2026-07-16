"""SQL repository for the execution resolver (§14.9).

Resolves the `core.series_members` leg whose market-time validity window
(`valid_from`/`valid_to`, epoch ms) covers the requested `as_of` instant, then
joins the current `public.instruments` state for that leg's `source_symbol`.
`known_from`/`known_to` on `series_members` are filtered with the same
`as_of` used for the market-time window, so a backtest replay never sees
membership knowledge that would not have been known at that instant.
"""

from __future__ import annotations

from datetime import UTC, datetime
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

FIND_ACTIVE_MEMBER_SQL = """
SELECT
    m.source_venue,
    m.source_symbol,
    m.valid_from,
    m.valid_to,
    i.state AS instrument_state
FROM core.series_members m
LEFT JOIN public.instruments i ON i.symbol = m.source_symbol
WHERE m.series_id = :series_id
  AND m.valid_from <= CAST(:as_of_ms AS bigint)
  AND (m.valid_to IS NULL OR m.valid_to > CAST(:as_of_ms AS bigint))
  AND m.known_from <= :as_of
  AND (m.known_to IS NULL OR m.known_to > :as_of)
ORDER BY m.valid_from DESC, m.known_from DESC
LIMIT 1
""".strip()


class SqlExecutionResolverRepository:
    async def resolve_alias(self, series_id: str, as_of: datetime) -> str:
        async with get_db_session() as session:
            result = await session.execute(
                text(RESOLVE_ALIAS_SQL), {"series_id": series_id, "as_of": as_of}
            )
            resolved = result.scalar_one_or_none()
        return str(resolved) if resolved is not None else series_id

    async def find_active_member(
        self, series_id: str, as_of: datetime
    ) -> Mapping[str, object] | None:
        async with get_db_session() as session:
            result = await session.execute(
                text(FIND_ACTIVE_MEMBER_SQL),
                {
                    "series_id": series_id,
                    "as_of": as_of,
                    "as_of_ms": _as_of_ms(as_of),
                },
            )
            row = result.mappings().one_or_none()
        return dict(row) if row is not None else None


def _as_of_ms(value: datetime) -> int:
    resolved = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return int(resolved.timestamp() * 1000)
