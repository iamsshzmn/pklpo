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
from .schema_cache import SchemaCache, SchemaInfo, get_or_load_schema, get_schema_cache
from .upsert_executor import execute_upsert_with_retry

__all__ = [
    # Main entry point
    "insert_indicators",
    # Data transformation
    "convert_timestamps_to_int64",
    "normalize_numeric_values",
    "filter_records_by_schema",
    "validate_pk_fields",
    "validate_service_fields",
    "get_numeric_columns_from_table",
    "transform_records_for_upsert",
    # Schema caching
    "SchemaCache",
    "SchemaInfo",
    "get_schema_cache",
    "get_or_load_schema",
    # UPSERT execution
    "execute_upsert_with_retry",
]
