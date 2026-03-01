from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import pandas as pd


class IndicatorDataProvider(Protocol):
    def load(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame: ...
