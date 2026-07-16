"""Execution resolver: what venue symbol can be traded as_of? (§14.9)

Distinct service from the candles facade:

    candles facade answers: what history should analysis read?
    execution resolver answers: what venue symbol can be traded as_of?

It must never infer tradeability from "last source_symbol in continuous
history" — that would silently route live orders to a delisted symbol once a
succession stops appearing in fresh candle data. Instead it resolves the
`core.series_members` leg whose market-time validity window
(`valid_from`/`valid_to`) actually covers `as_of`, then reports the current
instrument state for that leg's `source_symbol`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

LIVE_INSTRUMENT_STATE = "live"


@dataclass(frozen=True)
class ExecutionResolution:
    series_id: str
    venue: str | None
    source_symbol: str | None
    is_tradeable: bool
    valid_from: int | None
    valid_to: int | None
    instrument_state: str | None
    reason: str


@dataclass(frozen=True)
class ActiveMemberRow:
    source_venue: str
    source_symbol: str
    valid_from: int
    valid_to: int | None
    instrument_state: str | None


class ExecutionResolverRepository(Protocol):
    async def resolve_alias(self, series_id: str, as_of: datetime) -> str:
        """Resolve a PIT alias to the canonical series id."""

    async def find_active_member(
        self, series_id: str, as_of: datetime
    ) -> Mapping[str, object] | ActiveMemberRow | None:
        """Find the series_members leg whose validity window covers as_of."""


class ExecutionResolver:
    def __init__(self, repository: ExecutionResolverRepository) -> None:
        self._repository = repository

    async def resolve_execution_symbol(
        self, series_id: str, as_of: datetime
    ) -> ExecutionResolution:
        canonical_series_id = await self._repository.resolve_alias(series_id, as_of)
        raw_member = await self._repository.find_active_member(
            canonical_series_id, as_of
        )

        if raw_member is None:
            return ExecutionResolution(
                series_id=canonical_series_id,
                venue=None,
                source_symbol=None,
                is_tradeable=False,
                valid_from=None,
                valid_to=None,
                instrument_state=None,
                reason="no_active_member_at_as_of",
            )

        member = _coerce_member(raw_member)
        is_tradeable = member.instrument_state == LIVE_INSTRUMENT_STATE
        if member.instrument_state is None:
            reason = "member_active_instrument_state_unknown"
        elif is_tradeable:
            reason = "member_active_and_instrument_live"
        else:
            reason = "member_active_instrument_not_live"

        return ExecutionResolution(
            series_id=canonical_series_id,
            venue=member.source_venue,
            source_symbol=member.source_symbol,
            is_tradeable=is_tradeable,
            valid_from=member.valid_from,
            valid_to=member.valid_to,
            instrument_state=member.instrument_state,
            reason=reason,
        )


def _coerce_member(
    row: Mapping[str, object] | ActiveMemberRow,
) -> ActiveMemberRow:
    if isinstance(row, ActiveMemberRow):
        return row

    valid_to = row.get("valid_to")
    instrument_state = row.get("instrument_state")
    return ActiveMemberRow(
        source_venue=str(row["source_venue"]),
        source_symbol=str(row["source_symbol"]),
        valid_from=int(row["valid_from"]),
        valid_to=None if valid_to is None else int(valid_to),
        instrument_state=None if instrument_state is None else str(instrument_state),
    )
