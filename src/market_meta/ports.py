"""Market metadata ports."""

from __future__ import annotations

from typing import Protocol


class InstrumentLookupPort(Protocol):
    async def instrument_exists(self, symbol: str) -> bool:
        """Return whether ``symbol`` exists in the instrument catalog."""
        ...


class InstrumentRepositoryPort(InstrumentLookupPort, Protocol):
    async def find_missing_symbols(self, symbols: list[str]) -> list[str]:
        """Return symbols absent from the instrument catalog."""
        ...
