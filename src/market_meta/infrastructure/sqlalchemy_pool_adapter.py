from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

_PG_PLACEHOLDER_RE = re.compile(r"\$(\d+)")


def _convert_pg_placeholders(query: str) -> str:
    """Convert asyncpg-style placeholders ($1, $2, ...) to SQLAlchemy named params."""
    return _PG_PLACEHOLDER_RE.sub(lambda m: f":p{m.group(1)}", query)


def _build_params(args: tuple[Any, ...]) -> dict[str, Any]:
    return {f"p{idx + 1}": value for idx, value in enumerate(args)}


class SQLAlchemyConnectionAdapter:
    """Subset of asyncpg Connection API used by quality pipeline code."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        stmt = text(_convert_pg_placeholders(query))
        result = await self._connection.execute(stmt, _build_params(args))
        return list(result.fetchall())

    async def fetchval(self, query: str, *args: Any) -> Any:
        rows = await self.fetch(query, *args)
        if not rows:
            return None
        return rows[0][0]

    async def execute(self, query: str, *args: Any) -> str:
        stmt = text(_convert_pg_placeholders(query))
        result = await self._connection.execute(stmt, _build_params(args))
        affected = result.rowcount if result.rowcount is not None else 0
        return f"EXECUTE {affected}"

    async def executemany(
        self,
        query: str,
        seq_of_params: list[tuple[Any, ...]],
    ) -> None:
        if not seq_of_params:
            return
        stmt = text(_convert_pg_placeholders(query))
        payload = [_build_params(args) for args in seq_of_params]
        await self._connection.execute(stmt, payload)


class SQLAlchemyPoolAdapter:
    """Subset of asyncpg Pool API used by quality pipeline code."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def acquire(self):
        async with self._engine.begin() as connection:
            yield SQLAlchemyConnectionAdapter(connection)
