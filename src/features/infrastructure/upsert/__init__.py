"""Backward-compatible UPSERT helper package."""

from .batch_sizer import (
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_MIN_BATCH_SIZE,
    DIAGNOSTIC_SINGLE_ROW,
    TARGET_SQL_PARAMS,
    _get_dynamic_batch_size,
)
from .column_introspector import get_numeric_columns, load_db_columns
from .sql_generator import (
    _clip_numeric_value,
    _normalize_value,
    build_and_execute_upsert,
    build_upsert_statement,
    execute_upsert,
    sanitize_records,
)
from .type_validator import (
    assert_required_fields,
    filter_problematic_fields,
    sanitize_numeric_value,
    validate_numeric_types,
    validate_upsert_data,
)

__all__ = [
    "DEFAULT_MAX_BATCH_SIZE",
    "DEFAULT_MIN_BATCH_SIZE",
    "DIAGNOSTIC_SINGLE_ROW",
    "TARGET_SQL_PARAMS",
    "_clip_numeric_value",
    "_get_dynamic_batch_size",
    "_normalize_value",
    "assert_required_fields",
    "build_and_execute_upsert",
    "build_upsert_statement",
    "execute_upsert",
    "filter_problematic_fields",
    "get_numeric_columns",
    "load_db_columns",
    "sanitize_numeric_value",
    "sanitize_records",
    "validate_numeric_types",
    "validate_upsert_data",
]
