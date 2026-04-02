"""Compatibility wrapper around the split schema registry/synchronizer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..domain.indicator_schema_registry import IndicatorSchemaRegistry
from ..infrastructure.indicator_schema_synchronizer import IndicatorSchemaSynchronizer

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


class SchemaManager:
    """Deprecated facade kept while callers migrate to registry/synchronizer."""

    def __init__(self, schema_path: str | Path | None = None):
        self.registry = IndicatorSchemaRegistry(schema_path=schema_path)
        self.synchronizer = IndicatorSchemaSynchronizer(self.registry)
        self.schema_path = self.registry.schema_path
        self.schema = self.registry.schema

    def get_all_columns(self) -> set[str]:
        return self.registry.get_all_columns()

    def get_column_info(self, column_name: str) -> dict[str, Any]:
        return self.registry.get_column_info(column_name)

    def get_column_explanation(self, column_name: str) -> str:
        return self.registry.get_column_explanation(column_name)

    def get_name_mapping(self) -> dict[str, str]:
        return self.registry.get_name_mapping()

    def get_aliases(self) -> dict[str, str]:
        return self.registry.get_aliases()

    def resolve_alias(self, name: str) -> str:
        return self.registry.resolve_alias(name)

    def resolve_aliases_in_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.registry.resolve_aliases_in_dict(data)

    def get_required_fields(self) -> set[str]:
        return self.registry.get_required_fields()

    async def sync_database_schema(self, session: AsyncSession) -> dict[str, Any]:
        return await self.synchronizer.sync_database_schema(session)

    async def _get_db_columns(self, session: AsyncSession) -> set[str]:
        return await self.synchronizer.get_db_columns(session)

    def validate_data(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        return self.registry.validate_data(records)

    def get_schema_info(self) -> dict[str, Any]:
        return self.registry.get_schema_info()
