from __future__ import annotations


class InstrumentNotFoundError(Exception):
    """Raised when an instrument symbol is not found in the instruments table or OKX API."""

    def __init__(self, symbol: str) -> None:
        super().__init__(f"Instrument not found: {symbol!r}")
        self.symbol = symbol
