"""Market metadata domain exceptions."""

from __future__ import annotations


class InstrumentNotFoundError(ValueError):
    """Raised when an instrument is absent from the registered catalog."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"Instrument not found: {symbol}")
