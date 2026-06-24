"""Instrument validation use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.market_meta.domain.exceptions import InstrumentNotFoundError

if TYPE_CHECKING:
    from src.market_meta.ports import InstrumentLookupPort


async def validate_instrument_exists(
    symbol: str,
    *,
    repository: InstrumentLookupPort,
) -> None:
    """Raise when ``symbol`` is absent from the instrument repository."""
    if not await repository.instrument_exists(symbol):
        raise InstrumentNotFoundError(symbol)
