"""Persistence-related ports for features application use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd


@dataclass(frozen=True, slots=True)
class RepositoryStorageProfile:
    """Metadata describing a repository backend and its storage targets."""

    backend: str
    targets: tuple[str, ...]
    table_name: str | None = None

    @property
    def primary_target(self) -> str | None:
        """Return the first configured target, if any."""
        return self.targets[0] if self.targets else None


@runtime_checkable
class IndicatorRepository(Protocol):
    """Persistence abstraction for batched indicator storage."""

    def describe_storage(self) -> RepositoryStorageProfile: ...

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
