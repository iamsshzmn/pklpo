"""Application use case for indicator schema synchronization."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class IndicatorSchemaSyncPort(Protocol):
    """Application-facing contract for schema synchronization."""

    async def sync_database_schema(
        self, session: AsyncSession
    ) -> dict[str, object]: ...


class SyncIndicatorSchemaUseCase:
    """Runs schema synchronization through an injected infrastructure adapter."""

    def __init__(self, synchronizer: IndicatorSchemaSyncPort):
        self._synchronizer = synchronizer

    async def execute(self, session: AsyncSession) -> dict[str, object]:
        return await self._synchronizer.sync_database_schema(session)
