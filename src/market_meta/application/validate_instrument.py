from __future__ import annotations

from typing import TYPE_CHECKING

from src.market_meta.domain.exceptions import InstrumentNotFoundError

if TYPE_CHECKING:
    from src.market_meta.ports import InstrumentRepositoryPort


async def validate_instrument_exists(
    symbol: str,
    *,
    repository: InstrumentRepositoryPort,
) -> None:
    """Raise InstrumentNotFoundError if symbol is not present in the instruments table."""
    if not await repository.instrument_exists(symbol):
        raise InstrumentNotFoundError(symbol)
