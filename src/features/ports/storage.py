"""Storage-related ports for features application use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import pandas as pd
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..bootstrap import FeatureSaveDependencies


class FeatureStorageGateway(Protocol):
    """Abstract access to feature-related storage reads and schema maintenance."""

    async def fetch_latest_ts(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str,
    ) -> int | None: ...

    async def fetch_ohlcv_df(
        self,
        session: AsyncSession,
        symbol: str,
        timeframe: str,
        *,
        since_ts: int | None = None,
        until_ts: int | None = None,
        limit: int = 200,
    ) -> pd.DataFrame | None: ...

    async def ensure_indicator_columns(
        self,
        session: AsyncSession,
        table: str,
        columns: list[str],
    ) -> None: ...


class FeatureSaveDependenciesFactory(Protocol):
    """Factory for assembling save dependencies at the composition root."""

    def __call__(self, session: AsyncSession) -> FeatureSaveDependencies: ...
