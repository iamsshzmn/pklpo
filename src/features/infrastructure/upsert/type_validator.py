from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

import numpy as np

from src.logging import LogCategory, Verbosity, get_category_logger, should_log

logger = get_category_logger(LogCategory.INSERT)


def validate_numeric_types(
    records: list[dict[str, Any]],
    numeric_columns: set[str],
    row_offset: int = 0,
) -> None:
    """Validate that numeric fields contain acceptable Python numeric values."""
    if not records:
        return

    errors: list[str] = []
    for row_idx, row in enumerate(records):
        actual_idx = row_offset + row_idx
        for col in numeric_columns:
            if col not in row:
                continue

            val = row[col]
            if val is None:
                continue

            if isinstance(val, str):
                errors.append(
                    f"Row {actual_idx}: column '{col}' is str: {val!r} (type: {type(val).__name__})"
                )
                continue

            if isinstance(val, int | float | Decimal | np.number):
                if isinstance(val, float | np.floating):
                    if not math.isfinite(val):
                        errors.append(
                            f"Row {actual_idx}: column '{col}' not finite: {val!r}"
                        )
                elif isinstance(val, np.integer):
                    pass
                continue

            errors.append(
                f"Row {actual_idx}: column '{col}' has invalid type {type(val).__name__}: {val!r}"
            )

    if errors:
        error_msg = f"Type validation failed for {len(errors)} values:\n" + "\n".join(
            errors[:20]
        )
        if len(errors) > 20:
            error_msg += f"\n... and {len(errors) - 20} more errors"
        logger.error(error_msg)
        raise TypeError(error_msg)


def assert_required_fields(records: list[dict[str, Any]], required: set[str]) -> None:
    """Validate that all records contain the required keys."""
    if not records:
        raise ValueError("No records provided")

    first_record = records[0]
    missing_fields = required - set(first_record.keys())
    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    for i, record in enumerate(records):
        missing_in_record = required - set(record.keys())
        if missing_in_record:
            raise ValueError(f"Record {i} missing required fields: {missing_in_record}")


def filter_problematic_fields(
    records: list[dict[str, Any]], problematic_fields: list[str] | None = None
) -> list[dict[str, Any]]:
    """Remove fields that should not participate in the UPSERT payload."""
    if problematic_fields is None:
        problematic_fields = []

    if not problematic_fields:
        return records

    filtered_records = []
    for record in records:
        filtered_record = {
            k: v for k, v in record.items() if k not in problematic_fields
        }
        filtered_records.append(filtered_record)

    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Filtered out {len(problematic_fields)} problematic fields")
    return filtered_records


def sanitize_numeric_value(value: Any) -> float | None:
    """Normalize numeric-like values to float, mapping NaN/inf to None."""
    if value is None:
        return None

    try:
        float_val = float(value)
        if np.isnan(float_val) or np.isinf(float_val):
            return None
        return float_val
    except (ValueError, TypeError, OverflowError) as e:
        logger.debug(f"Cannot convert {value} to float: {e}")
        return None


def validate_upsert_data(
    records: list[dict[str, Any]], db_cols: set[str], required_fields: set[str]
) -> None:
    """Run the required-field and numeric hygiene checks before UPSERT."""
    assert_required_fields(records, required_fields)

    critical_fields = ["ics_26", "rma_20", "t3_20"]
    missing_critical = []
    for field in critical_fields:
        if field in db_cols and not any(field in record for record in records):
            missing_critical.append(field)

    if missing_critical and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
        logger.warning(f"Critical fields missing from all records: {missing_critical}")

    type_warnings = 0
    for record in records:
        for key, value in record.items():
            if key in db_cols and isinstance(value, int | float | np.number):
                try:
                    sanitize_numeric_value(value)
                except ValueError:
                    type_warnings += 1

    if type_warnings > 0 and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Type warnings during validation: {type_warnings}")


__all__ = [
    "assert_required_fields",
    "filter_problematic_fields",
    "sanitize_numeric_value",
    "validate_numeric_types",
    "validate_upsert_data",
]
