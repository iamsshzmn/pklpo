from __future__ import annotations

from typing import Protocol


class InstrumentRepositoryPort(Protocol):
    async def instrument_exists(self, symbol: str) -> bool: ...
