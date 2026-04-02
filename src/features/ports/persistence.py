"""Persistence-related ports for features application use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@runtime_checkable
class IndicatorRepository(Protocol):
    """Persistence abstraction for batched indicator storage."""

    async def save_batch(
        self,
        records: list[dict],
        symbol: str,
        timeframe: str,
    ) -> int: ...

    async def save_batch_from_df(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> int: ...

    async def validate_connection(self) -> dict[str, object]: ...

    async def verify_integrity(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, object]: ...
