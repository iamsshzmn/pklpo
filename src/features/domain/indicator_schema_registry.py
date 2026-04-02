"""Pure registry API for indicator schema metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.logging import get_logger

logger = get_logger(__name__)


class IndicatorSchemaRegistry:
    """Loads the canonical indicator schema and validates feature records."""

    def __init__(self, schema_path: str | Path | None = None):
        if schema_path is None:
            self.schema_path = (
                Path(__file__).parent.parent / "schema" / "indicators_schema.yml"
            )
        else:
            self.schema_path = Path(schema_path)
        self.schema = self._load_schema()
        self._all_columns = self._build_column_registry()

    def _load_schema(self) -> dict[str, Any]:
        try:
            with open(self.schema_path, encoding="utf-8") as f:
                schema: dict[str, Any] = yaml.safe_load(f) or {}
            logger.info("Loaded schema version %s", schema.get("version", "unknown"))
            return schema
        except Exception as e:
            logger.error("Failed to load schema: %s", e)
            raise

    def _build_column_registry(self) -> dict[str, dict[str, Any]]:
        registry: dict[str, dict[str, Any]] = {}

        for pk in self.schema.get("primary_keys", []):
            registry[pk["name"]] = {
                "type": pk["type"],
                "nullable": pk.get("nullable", False),
                "description": pk.get("description", ""),
                "category": "primary_key",
            }

        for field in self.schema.get("service_fields", []):
            registry[field["name"]] = {
                "type": field["type"],
                "nullable": field.get("nullable", True),
                "description": field.get("description", ""),
                "category": "service",
            }

        for category, indicators_list in self.schema.get("indicators", {}).items():
            for indicator in indicators_list:
                registry[indicator["name"]] = {
                    "type": indicator["type"],
                    "nullable": indicator.get("nullable", True),
                    "description": indicator.get("description", ""),
                    "category": category,
                }

        logger.info("Built registry with %d columns", len(registry))
        return registry

    def get_all_columns(self) -> set[str]:
        return set(self._all_columns.keys())

    def get_column_info(self, column_name: str) -> dict[str, Any]:
        return self._all_columns.get(column_name, {})

    def get_column_explanation(self, column_name: str) -> str:
        col_info = self.get_column_info(column_name)
        explanation: str = col_info.get("explanation", "") or col_info.get(
            "description", ""
        )
        return explanation if isinstance(explanation, str) else ""

    def get_name_mapping(self) -> dict[str, str]:
        mapping = self.schema.get("name_mapping", {})
        return mapping if isinstance(mapping, dict) else {}

    def get_aliases(self) -> dict[str, str]:
        aliases = self.schema.get("aliases", {})
        return aliases if isinstance(aliases, dict) else {}

    def resolve_alias(self, name: str) -> str:
        return self.get_aliases().get(name, name)

    def resolve_aliases_in_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        aliases = self.get_aliases()
        return {aliases.get(key, key): value for key, value in data.items()}

    def get_required_fields(self) -> set[str]:
        return set(self.schema.get("validation", {}).get("required_fields", []))

    def validate_data(self, records: list[dict[str, Any]]) -> dict[str, Any]:
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
            missing_required = required_fields - set(record.keys())
            if missing_required:
                validation_result["errors"].append(
                    f"Record {i}: Missing required fields: {missing_required}"
                )
                validation_result["valid"] = False
                continue

            mapped_record = {}
            for key, value in record.items():
                mapped_key = name_mapping.get(key, key)
                if mapped_key not in all_columns:
                    validation_result["warnings"].append(
                        f"Record {i}: Unknown column '{key}' -> '{mapped_key}'"
                    )
                    continue

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
            "Validation completed: %d valid records",
            len(validation_result["mapped_records"]),
        )
        return validation_result

    def _validate_value(self, column_name: str, value: Any) -> bool:
        if value is None:
            return True

        column_info = self.get_column_info(column_name)
        if not column_info:
            return False

        column_type = column_info["type"]
        if column_type.startswith("DECIMAL"):
            try:
                float(value)
                return True
            except (ValueError, TypeError):
                return False

        if column_type.startswith("VARCHAR"):
            return isinstance(value, str)

        if column_type == "BIGINT":
            try:
                int(value)
                return True
            except (ValueError, TypeError):
                return False

        return True

    def get_schema_info(self) -> dict[str, Any]:
        return {
            "version": self.schema.get("version"),
            "total_columns": len(self._all_columns),
            "categories": list(self.schema.get("indicators", {}).keys()),
            "last_updated": self.schema.get("last_updated"),
        }
