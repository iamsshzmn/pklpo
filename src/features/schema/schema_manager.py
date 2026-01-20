"""
Схема-менеджер для управления единым реестром колонок indicators.
Единый источник истины для синхронизации БД, валидации и маппинга.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SchemaManager:
    """Менеджер единого реестра колонок."""

    def __init__(self, schema_path: str = "src/features/schema/indicators_schema.yml"):
        self.schema_path = Path(schema_path)
        self.schema = self._load_schema()
        self._all_columns = self._build_column_registry()

    def _load_schema(self) -> dict[str, Any]:
        """Загружает схему из YAML файла."""
        try:
            with open(self.schema_path, encoding="utf-8") as f:
                schema: dict[str, Any] = yaml.safe_load(f) or {}
            logger.info(f"Loaded schema version {schema.get('version', 'unknown')}")
            return schema
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            raise

    def _build_column_registry(self) -> dict[str, dict[str, Any]]:
        """Строит полный реестр всех колонок."""
        registry = {}

        # Добавляем PK поля
        for pk in self.schema.get("primary_keys", []):
            registry[pk["name"]] = {
                "type": pk["type"],
                "nullable": pk.get("nullable", False),
                "description": pk.get("description", ""),
                "category": "primary_key",
            }

        # Добавляем служебные поля
        for field in self.schema.get("service_fields", []):
            registry[field["name"]] = {
                "type": field["type"],
                "nullable": field.get("nullable", True),
                "description": field.get("description", ""),
                "category": "service",
            }

        # Добавляем индикаторы по группам
        indicators = self.schema.get("indicators", {})
        for category, indicators_list in indicators.items():
            for indicator in indicators_list:
                registry[indicator["name"]] = {
                    "type": indicator["type"],
                    "nullable": indicator.get("nullable", True),
                    "description": indicator.get("description", ""),
                    "category": category,
                }

        logger.info(f"Built registry with {len(registry)} columns")
        return registry

    def get_all_columns(self) -> set[str]:
        """Возвращает множество всех колонок."""
        return set(self._all_columns.keys())

    def get_column_info(self, column_name: str) -> dict[str, Any]:
        """
        Returns information about a column.

        Args:
            column_name: Name of the column

        Returns:
            Dictionary with column metadata including:
            - type: SQL type
            - nullable: Whether nullable
            - description: Short description
            - explanation: Detailed explanation (for LLM)
            - category: Indicator category
        """
        return self._all_columns.get(column_name, {})

    def get_column_explanation(self, column_name: str) -> str:
        """
        Get human-readable explanation of an indicator for LLM/documentation.

        Args:
            column_name: Name of the indicator

        Returns:
            Explanation string, or empty string if not found
        """
        col_info = self.get_column_info(column_name)
        explanation: str = col_info.get("explanation", "") or col_info.get(
            "description", ""
        )
        return explanation if isinstance(explanation, str) else ""

    def get_name_mapping(self) -> dict[str, str]:
        """Возвращает маппинг имен."""
        mapping = self.schema.get("name_mapping", {})
        return mapping if isinstance(mapping, dict) else {}

    def get_aliases(self) -> dict[str, str]:
        """
        Returns alias mapping for indicator names.

        Maps alternative names (e.g., from pandas_ta) to canonical names.

        Returns:
            Dictionary mapping alias -> canonical_name
        """
        aliases = self.schema.get("aliases", {})
        return aliases if isinstance(aliases, dict) else {}

    def resolve_alias(self, name: str) -> str:
        """
        Resolve an indicator name through the alias system.

        Args:
            name: Indicator name (possibly an alias)

        Returns:
            Canonical name (or original name if not an alias)
        """
        aliases = self.get_aliases()
        return aliases.get(name, name)

    def resolve_aliases_in_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve all aliases in a dictionary of indicator values.

        Args:
            data: Dictionary with possibly aliased names

        Returns:
            Dictionary with canonical names
        """
        aliases = self.get_aliases()
        resolved = {}
        for key, value in data.items():
            canonical_key = aliases.get(key, key)
            resolved[canonical_key] = value
        return resolved

    def get_required_fields(self) -> set[str]:
        """Возвращает обязательные поля."""
        return set(self.schema.get("validation", {}).get("required_fields", []))

    async def sync_database_schema(self, session: AsyncSession) -> dict[str, Any]:
        """
        Синхронизирует схему БД с реестром.
        Добавляет отсутствующие колонки, логирует лишние.
        """
        logger.info("Starting database schema synchronization...")

        # Получаем текущие колонки БД
        db_columns = await self._get_db_columns(session)
        registry_columns = self.get_all_columns()

        # Находим различия
        missing_in_db = registry_columns - db_columns
        extra_in_db = db_columns - registry_columns

        sync_result = {
            "missing_columns": list(missing_in_db),
            "extra_columns": list(extra_in_db),
            "added_columns": [],
            "errors": [],
        }

        # Добавляем отсутствующие колонки
        for column_name in missing_in_db:
            try:
                await self._add_column(session, column_name)
                sync_result["added_columns"].append(column_name)
                logger.info(f"Added column: {column_name}")
            except Exception as e:
                error_msg = f"Failed to add column {column_name}: {e}"
                sync_result["errors"].append(error_msg)
                logger.error(error_msg)

        # Логируем лишние колонки
        if extra_in_db:
            logger.warning(
                f"Extra columns in DB (not in registry): {sorted(extra_in_db)}"
            )

        logger.info(
            f"Schema sync completed: {len(sync_result['added_columns'])} added, {len(sync_result['extra_columns'])} extra"
        )
        return sync_result

    async def _get_db_columns(self, session: AsyncSession) -> set[str]:
        """Получает список колонок из БД."""
        query = text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'indicators'
            AND table_schema = 'public'
        """
        )

        result = await session.execute(query)
        columns = {
            row[0] for row in result.all()
        }  # FIXED: .all() instead of .fetchall() for async
        logger.info(f"Found {len(columns)} columns in database")
        return columns

    async def _add_column(self, session: AsyncSession, column_name: str) -> None:
        """Добавляет колонку в БД."""
        column_info = self.get_column_info(column_name)
        if not column_info:
            raise ValueError(f"Column {column_name} not found in registry")

        column_type = column_info["type"]
        nullable = column_info.get("nullable", True)

        nullable_clause = "" if nullable else "NOT NULL"

        alter_sql = f"""
            ALTER TABLE indicators
            ADD COLUMN {column_name} {column_type} {nullable_clause}
        """

        await session.execute(text(alter_sql))
        logger.info(f"Added column {column_name} with type {column_type}")

    def validate_data(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Валидирует данные перед UPSERT.
        Проверяет типы, обязательные поля, маппинг имен.
        """
        validation_result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "mapped_records": [],
        }

        required_fields = self.get_required_fields()
        name_mapping = self.get_name_mapping()
        all_columns = self.get_all_columns()

        for i, record in enumerate(records):
            # Проверяем обязательные поля
            missing_required = required_fields - set(record.keys())
            if missing_required:
                validation_result["errors"].append(
                    f"Record {i}: Missing required fields: {missing_required}"
                )
                validation_result["valid"] = False
                continue

            # Применяем маппинг имен
            mapped_record = {}
            for key, value in record.items():
                mapped_key = name_mapping.get(key, key)
                if mapped_key not in all_columns:
                    validation_result["warnings"].append(
                        f"Record {i}: Unknown column '{key}' -> '{mapped_key}'"
                    )
                    continue

                # Валидируем значение
                if not self._validate_value(mapped_key, value):
                    validation_result["warnings"].append(
                        f"Record {i}: Invalid value for {mapped_key}: {value}"
                    )
                    continue

                mapped_record[mapped_key] = value

            validation_result["mapped_records"].append(mapped_record)

        if validation_result["errors"]:
            validation_result["valid"] = False

        logger.info(
            f"Validation completed: {len(validation_result['mapped_records'])} valid records"
        )
        return validation_result

    def _validate_value(self, column_name: str, value: Any) -> bool:
        """Валидирует значение для колонки."""
        if value is None:
            return True

        column_info = self.get_column_info(column_name)
        if not column_info:
            return False

        # Простая валидация типов
        if column_info["type"].startswith("DECIMAL"):
            try:
                float(value)
                return True
            except (ValueError, TypeError):
                return False

        if column_info["type"].startswith("VARCHAR"):
            return isinstance(value, str)

        if column_info["type"] == "BIGINT":
            try:
                int(value)
                return True
            except (ValueError, TypeError):
                return False

        return True

    def get_reflected_table(self, session: AsyncSession) -> Table:
        """Возвращает таблицу indicators из модели (без reflection)."""
        # ИСПРАВЛЕНО: autoload_with вызывает greenlet_spawn в async контексте
        # Используем уже определенную модель вместо синхронного reflection
        from src.models import Indicator

        table: Table = Indicator.__table__
        return table

    def get_schema_info(self) -> dict[str, Any]:
        """Возвращает информацию о схеме."""
        return {
            "version": self.schema.get("version"),
            "total_columns": len(self._all_columns),
            "categories": list(self.schema.get("indicators", {}).keys()),
            "last_updated": self.schema.get("last_updated"),
        }
