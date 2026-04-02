"""
Persistence layer for indicators insertion.

This package provides modules for validating, normalizing, and inserting
indicator data into the database.

REFACTORED (Stage 2):
- data_transformer.py: Type conversions and normalization
- schema_cache.py: Schema caching to avoid repeated DB reflection
- upsert_executor.py: UPSERT with retry logic
- inserter.py: Orchestration only
"""

from .data_transformer import (
    convert_timestamps_to_int64,
    filter_records_by_schema,
    get_numeric_columns_from_table,
    normalize_numeric_values,
    transform_records_for_upsert,
    validate_pk_fields,
    validate_service_fields,
)
from .inserter import insert_indicators
from .repository import SqlAlchemyIndicatorRepository, create_indicator_repository
from .schema_cache import SchemaCache, SchemaInfo, get_or_load_schema, get_schema_cache
from .upsert_executor import execute_upsert_with_retry

__all__ = [
    "SchemaCache",
    "SchemaInfo",
    "SqlAlchemyIndicatorRepository",
    "convert_timestamps_to_int64",
    "create_indicator_repository",
    "execute_upsert_with_retry",
    "filter_records_by_schema",
    "get_numeric_columns_from_table",
    "get_or_load_schema",
    "get_schema_cache",
    "insert_indicators",
    "normalize_numeric_values",
    "transform_records_for_upsert",
    "validate_pk_fields",
    "validate_service_fields",
]
