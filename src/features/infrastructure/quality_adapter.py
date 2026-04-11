from __future__ import annotations

import re
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

    from src.features.ports.quality import (
        QualityConnectionProtocol,
        QualityEngineProtocol,
        QualityReportProtocol,
    )

from src.candles.application.quality_pipeline import run_quality_pipeline

_PG_PLACEHOLDER_RE = re.compile(r"\$(\d+)")


def _convert_pg_placeholders(query: str) -> str:
    return _PG_PLACEHOLDER_RE.sub(lambda match: f":p{match.group(1)}", query)


def _build_params(args: tuple[object, ...]) -> dict[str, object]:
    return {f"p{idx + 1}": value for idx, value in enumerate(args)}


class _SQLAlchemyQualityConnectionAdapter:
    """Subset of asyncpg connection API used by the quality pipeline."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def fetch(self, query: str, *args: object) -> list[object]:
        stmt = text(_convert_pg_placeholders(query))
        result = await self._connection.execute(stmt, _build_params(args))
        return list(result.fetchall())

    async def fetchval(self, query: str, *args: object) -> object:
        rows = await self.fetch(query, *args)
        if not rows:
            return None
        return rows[0][0]

    async def execute(self, query: str, *args: object) -> str:
        stmt = text(_convert_pg_placeholders(query))
        result = await self._connection.execute(stmt, _build_params(args))
        affected = result.rowcount if result.rowcount is not None else 0
        return f"EXECUTE {affected}"

    async def executemany(
        self,
        query: str,
        seq_of_params: list[tuple[object, ...]],
    ) -> None:
        if not seq_of_params:
            return
        stmt = text(_convert_pg_placeholders(query))
        payload = [_build_params(args) for args in seq_of_params]
        await self._connection.execute(stmt, payload)


class _SQLAlchemyQualityPoolAdapter:
    """SQLAlchemy-backed pool adapter local to the features boundary."""

    def __init__(self, engine: QualityEngineProtocol) -> None:
        self._engine = engine

    @asynccontextmanager
    async def acquire(
        self,
    ) -> AbstractAsyncContextManager[QualityConnectionProtocol]:
        async with self._engine.begin() as connection:
            yield _SQLAlchemyQualityConnectionAdapter(connection)


class SQLAlchemyQualityPipelineRunner:
    """Bridge the features validation flow to the candles quality pipeline."""

    async def __call__(
        self,
        engine: QualityEngineProtocol,
        *,
        send_alerts: bool = True,
        alert_cooldown_minutes: int = 30,
    ) -> tuple[QualityReportProtocol, dict[str, int]]:
        pool_adapter = _SQLAlchemyQualityPoolAdapter(engine)
        return await run_quality_pipeline(
            pool_adapter,
            send_alerts=send_alerts,
            alert_cooldown_minutes=alert_cooldown_minutes,
        )


def create_quality_pipeline_runner() -> SQLAlchemyQualityPipelineRunner:
    return SQLAlchemyQualityPipelineRunner()
