from __future__ import annotations

from typing import Protocol


class InstrumentRepositoryPort(Protocol):
    async def instrument_exists(self, symbol: str) -> bool: ...

    async def find_missing_symbols(self, symbols: list[str]) -> list[str]: ...
