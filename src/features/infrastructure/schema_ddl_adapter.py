"""Schema DDL adapter for features infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.db.db_schema_utils import ensure_columns
from src.features.ports import SchemaDDLPort

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemySchemaDDLAdapter(SchemaDDLPort):
    """Adapter that delegates schema DDL operations to shared db utilities."""

    async def ensure_columns(
        self,
        session: AsyncSession,
        table: str,
        columns: list[str],
    ) -> None:
        await ensure_columns(session, table, columns)


__all__ = ["SqlAlchemySchemaDDLAdapter"]
