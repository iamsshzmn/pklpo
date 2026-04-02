"""Ports for schema DDL operations in the features bounded context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class SchemaDDLPort(Protocol):
    """Abstract schema maintenance operations used by features infrastructure."""

    async def ensure_columns(
        self,
        session: AsyncSession,
        table: str,
        columns: list[str],
    ) -> None: ...


__all__ = ["SchemaDDLPort"]
