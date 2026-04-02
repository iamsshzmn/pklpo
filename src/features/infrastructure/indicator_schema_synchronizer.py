"""Infrastructure-only schema synchronization for indicators storage."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logging import get_logger

from ..domain.indicator_schema_registry import IndicatorSchemaRegistry
from ..storage_contract import IndicatorStorageContract

logger = get_logger(__name__)


class IndicatorSchemaSynchronizer:
    """Performs DB introspection and DDL sync using a pure registry."""

    def __init__(
        self,
        registry: IndicatorSchemaRegistry,
        *,
        table_name: str = IndicatorStorageContract.table_name,
    ) -> None:
        self.registry = registry
        self.table_name = table_name

    async def get_db_columns(self, session: AsyncSession) -> set[str]:
        query = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = :table_name
            AND table_schema = 'public'
        """
        )
        result = await session.execute(query, {"table_name": self.table_name})
        columns = {row[0] for row in result.all()}
        logger.info("Found %d columns in database", len(columns))
        return columns

    async def sync_database_schema(self, session: AsyncSession) -> dict[str, Any]:
        logger.info("Starting database schema synchronization...")
        db_columns = await self.get_db_columns(session)
        registry_columns = self.registry.get_all_columns()

        missing_in_db = registry_columns - db_columns
        extra_in_db = db_columns - registry_columns

        sync_result = {
            "missing_columns": list(missing_in_db),
            "extra_columns": list(extra_in_db),
            "added_columns": [],
            "errors": [],
        }

        for column_name in missing_in_db:
            try:
                await self._add_column(session, column_name)
                sync_result["added_columns"].append(column_name)
                logger.info("Added column: %s", column_name)
            except Exception as e:
                error_msg = f"Failed to add column {column_name}: {e}"
                sync_result["errors"].append(error_msg)
                logger.error(error_msg)

        if extra_in_db:
            logger.warning(
                "Extra columns in DB (not in registry): %s",
                sorted(extra_in_db),
            )

        logger.info(
            "Schema sync completed: %d added, %d extra",
            len(sync_result["added_columns"]),
            len(sync_result["extra_columns"]),
        )
        return sync_result

    async def _add_column(self, session: AsyncSession, column_name: str) -> None:
        column_info = self.registry.get_column_info(column_name)
        if not column_info:
            raise ValueError(f"Column {column_name} not found in registry")

        column_type = column_info["type"]
        nullable = column_info.get("nullable", True)
        nullable_clause = "" if nullable else "NOT NULL"

        alter_sql = f"""
            ALTER TABLE {self.table_name}
            ADD COLUMN {column_name} {column_type} {nullable_clause}
        """
        await session.execute(text(alter_sql))
        logger.info("Added column %s with type %s", column_name, column_type)
