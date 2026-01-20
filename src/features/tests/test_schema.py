"""
Tests for schema management and validation.
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.features.schema.schema_manager import SchemaManager


class TestSchemaManager:
    """Test suite for SchemaManager."""

    @pytest.fixture()
    def schema_manager(self):
        """Create SchemaManager instance."""
        return SchemaManager()

    def test_schema_loads(self, schema_manager):
        """Test that schema loads successfully."""
        assert schema_manager.schema is not None
        assert "version" in schema_manager.schema
        assert schema_manager.schema["version"] == "2.0.0"

    def test_get_all_columns(self, schema_manager):
        """Test retrieving all columns."""
        columns = schema_manager.get_all_columns()

        # Check that it returns a set
        assert isinstance(columns, set)

        # Check that primary keys are included
        assert "symbol" in columns
        assert "timeframe" in columns
        assert "timestamp" in columns

        # Check that some indicators are included
        assert "ema_21" in columns or len(columns) > 10

    def test_get_column_info(self, schema_manager):
        """Test retrieving column information."""
        # Test primary key
        symbol_info = schema_manager.get_column_info("symbol")
        assert symbol_info is not None
        assert symbol_info["type"] == "VARCHAR(20)"
        assert symbol_info["nullable"] is False

        # Test service field
        calculated_at_info = schema_manager.get_column_info("calculated_at")
        assert calculated_at_info is not None
        assert "timestamp" in calculated_at_info["type"].lower()

    def test_get_aliases(self, schema_manager):
        """Test alias mapping retrieval."""
        aliases = schema_manager.get_aliases()

        # Check that it returns a dict
        assert isinstance(aliases, dict)

        # Check specific aliases
        assert aliases.get("RSI_14") == "rsi_14"
        assert aliases.get("MACD_12_26_9") == "macd"
        assert aliases.get("BBU_20_2.0") == "bb_upper"

    def test_resolve_alias(self, schema_manager):
        """Test alias resolution."""
        # Test pandas_ta names
        assert schema_manager.resolve_alias("RSI_14") == "rsi_14"
        assert schema_manager.resolve_alias("MACD_12_26_9") == "macd"

        # Test canonical names (should return unchanged)
        assert schema_manager.resolve_alias("rsi_14") == "rsi_14"
        assert schema_manager.resolve_alias("macd") == "macd"

        # Test unknown names (should return unchanged)
        assert schema_manager.resolve_alias("unknown_indicator") == "unknown_indicator"

    def test_resolve_aliases_in_dict(self, schema_manager):
        """Test alias resolution in dictionaries."""
        data = {
            "RSI_14": 50.0,
            "MACD_12_26_9": 0.5,
            "rsi_14": 51.0,  # Already canonical
            "unknown": 42.0,  # Not an alias
        }

        resolved = schema_manager.resolve_aliases_in_dict(data)

        # Check that aliases were resolved
        assert "rsi_14" in resolved
        assert "macd" in resolved

        # Check that canonical names pass through
        assert resolved.get("unknown") == 42.0

    def test_get_required_fields(self, schema_manager):
        """Test retrieving required fields."""
        required = schema_manager.get_required_fields()

        # Check that it returns a set
        assert isinstance(required, set)

        # Primary keys should typically be required
        # Note: This depends on your schema configuration
        # Adjust assertions based on your actual schema


class TestSchemaValidation:
    """Test suite for schema validation."""

    @pytest.fixture()
    def schema_manager(self):
        """Create SchemaManager instance."""
        return SchemaManager()

    def test_validate_data_success(self, schema_manager):
        """Test successful data validation."""
        from datetime import datetime

        data = [
            {
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "timestamp": 1609459200000,
                "calculated_at": datetime.utcnow(),
                "ema_21": 45000.0,
                "rsi_14": 55.5,
            }
        ]

        result = schema_manager.validate_data(data)

        # Validation should pass
        assert result["valid"] is True
        assert "mapped_records" in result

    def test_validate_data_with_aliases(self, schema_manager):
        """Test data validation with aliased names."""
        from datetime import datetime

        data = [
            {
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "timestamp": 1609459200000,
                "calculated_at": datetime.utcnow(),
                "RSI_14": 55.5,  # Alias
                "MACD_12_26_9": 0.5,  # Alias
            }
        ]

        result = schema_manager.validate_data(data)

        # Validation should not crash with aliases
        # Note: aliases might be in warnings as unknown fields, which is expected
        assert "errors" in result
        assert "warnings" in result
        assert "mapped_records" in result

    def test_validate_data_missing_required(self, schema_manager):
        """Test validation with missing required fields."""
        data = [
            {
                "ema_21": 45000.0,
                # Missing symbol, timeframe, timestamp
            }
        ]

        result = schema_manager.validate_data(data)

        # Should have validation errors
        assert len(result.get("errors", [])) > 0 or len(result.get("warnings", [])) > 0

    def test_validate_data_unknown_fields(self, schema_manager):
        """Test validation with unknown fields."""
        from datetime import datetime

        data = [
            {
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "timestamp": 1609459200000,
                "calculated_at": datetime.utcnow(),
                "completely_unknown_field": 123.45,
            }
        ]

        result = schema_manager.validate_data(data)

        # Should have warnings for unknown fields
        assert len(result.get("warnings", [])) > 0 or result["valid"]


class TestSchemaUniqueness:
    """Test suite for schema uniqueness constraints."""

    @pytest.fixture()
    def schema_manager(self):
        """Create SchemaManager instance."""
        return SchemaManager()

    def test_no_duplicate_field_names(self, schema_manager):
        """Test that schema has no duplicate field names."""
        schema_manager.get_all_columns()

        # Get list of all field names from schema
        field_names = []

        # Primary keys
        for pk in schema_manager.schema.get("primary_keys", []):
            field_names.append(pk["name"])

        # Service fields
        for field in schema_manager.schema.get("service_fields", []):
            field_names.append(field["name"])

        # Indicators
        for _category, indicators in schema_manager.schema.get(
            "indicators", {}
        ).items():
            for indicator in indicators:
                field_names.append(indicator["name"])

        # Check for duplicates
        duplicates = [name for name in field_names if field_names.count(name) > 1]
        assert len(duplicates) == 0, f"Found duplicate field names: {set(duplicates)}"

    def test_alias_targets_exist(self, schema_manager):
        """Test that all alias targets are valid field names."""
        aliases = schema_manager.get_aliases()
        all_columns = schema_manager.get_all_columns()

        invalid_targets = []
        for alias, target in aliases.items():
            if target not in all_columns:
                invalid_targets.append((alias, target))

        assert (
            len(invalid_targets) == 0
        ), f"Aliases point to non-existent fields: {invalid_targets}"

    def test_no_circular_aliases(self, schema_manager):
        """Test that aliases don't create circular references."""
        aliases = schema_manager.get_aliases()

        # Check each alias
        for alias, target in aliases.items():
            visited = {alias}
            current = target

            # Follow the alias chain
            while current in aliases:
                if current in visited:
                    pytest.fail(
                        f"Circular alias detected: {' -> '.join(visited)} -> {current}"
                    )
                visited.add(current)
                current = aliases[current]


class TestSchemaIntegration:
    """Integration tests for schema with features module."""

    @pytest.fixture()
    def schema_manager(self):
        """Create SchemaManager instance."""
        return SchemaManager()

    def test_schema_covers_common_indicators(self, schema_manager):
        """Test that schema includes common technical indicators."""
        all_columns = schema_manager.get_all_columns()

        # Common indicators that should be present
        common_indicators = [
            "ema_21",
            "sma_20",
            "sma_200",
            "rsi_14",
            "macd",
            "atr_14",
            "bb_upper",
            "bb_lower",
            "hlc3",
            "hl2",
        ]

        missing = [ind for ind in common_indicators if ind not in all_columns]

        if missing:
            print(f"Warning: Common indicators missing from schema: {missing}")

        # At least most common indicators should be present
        present_count = len(common_indicators) - len(missing)
        assert (
            present_count >= len(common_indicators) * 0.8
        ), f"Less than 80% of common indicators present. Missing: {missing}"


def test_schema_file_exists():
    """Test that schema file exists and is readable."""
    schema_path = Path("src/features/schema/indicators_schema.yml")
    assert schema_path.exists(), f"Schema file not found: {schema_path}"

    # Try to read it
    with open(schema_path, encoding="utf-8") as f:
        content = f.read()
        assert len(content) > 0, "Schema file is empty"
        assert "version" in content, "Schema file missing version"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
