from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.types import BigInteger, Integer, Numeric

from src.features.observability.prometheus import get_metrics as get_prom_metrics
from src.features.storage_contract import IndicatorStorageContract
from src.logging import (
    LogAggregator,
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)

from .batch_sizer import (
    DEFAULT_MIN_BATCH_SIZE,
    DIAGNOSTIC_SINGLE_ROW,
    _get_dynamic_batch_size,
)
from .column_introspector import get_numeric_columns
from .type_validator import (
    filter_problematic_fields,
    sanitize_numeric_value,
    validate_numeric_types,
    validate_upsert_data,
)

logger = get_category_logger(LogCategory.INSERT)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _clip_numeric_value(value: float, precision: int, scale: int) -> float:
    max_value = 10 ** (precision - scale) - 10 ** (-scale)
    min_value = -max_value
    if value > max_value:
        return max_value
    if value < min_value:
        return min_value
    return value


def _normalize_value(value: Any, col_type: Any = None) -> Any:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        if isinstance(value, np.integer | np.int64 | np.int32 | np.int16 | np.int8):
            result = int(value)
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                result = int(
                    _clip_numeric_value(
                        float(result), col_type.precision, col_type.scale
                    )
                )
            return result

        if isinstance(value, np.floating | np.float64 | np.float32 | np.float16):
            float_val = float(value)
            if np.isnan(float_val) or np.isinf(float_val):
                return None
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                float_val = _clip_numeric_value(
                    float_val, col_type.precision, col_type.scale
                )
            return float_val

        if hasattr(pd, "Scalar") and isinstance(value, pd.Scalar):
            try:
                return _normalize_value(value.item(), col_type)
            except (AttributeError, ValueError):
                pass

        if isinstance(value, int | float):
            if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                return None
            result = value
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                result = _clip_numeric_value(
                    float(result), col_type.precision, col_type.scale
                )
            return result

        if hasattr(value, "item"):
            try:
                return _normalize_value(value.item(), col_type)
            except (AttributeError, ValueError):
                pass

        try:
            float_val = float(value)
            if np.isnan(float_val) or np.isinf(float_val):
                return None
            if (
                col_type
                and hasattr(col_type, "precision")
                and hasattr(col_type, "scale")
                and col_type.precision is not None
                and col_type.scale is not None
            ):
                float_val = _clip_numeric_value(
                    float_val, col_type.precision, col_type.scale
                )
            if float_val.is_integer():
                return int(float_val)
            return float_val
        except (ValueError, TypeError, OverflowError):
            pass

        return value
    except Exception as e:
        logger.debug(f"Failed to normalize value {value} ({type(value)}): {e}")
        return None


def sanitize_records(
    records: list[dict[str, Any]], db_cols: set[str]
) -> list[dict[str, Any]]:
    if not records:
        raise ValueError("No records to sanitize")

    sanitized: list[dict[str, Any]] = []
    total_fields = 0
    filtered_fields = 0

    for record in records:
        sanitized_record: dict[str, Any] = {}
        total_fields += len(record)
        for key, value in record.items():
            if key not in db_cols:
                filtered_fields += 1
                continue

            if value is None:
                sanitized_record[key] = None
            elif isinstance(value, pd.Series | pd.DataFrame):
                if len(value) > 0:
                    scalar_value = (
                        value.iloc[0]
                        if isinstance(value, pd.Series)
                        else value.iloc[0, 0]
                    )
                    if isinstance(scalar_value, int | float | np.number):
                        sanitized_record[key] = sanitize_numeric_value(scalar_value)
                    else:
                        sanitized_record[key] = (
                            None if pd.isna(scalar_value) else scalar_value
                        )
                else:
                    sanitized_record[key] = None
            elif isinstance(value, int | float | np.number):
                sanitized_record[key] = sanitize_numeric_value(value)
            else:
                if isinstance(value, str):
                    try:
                        sanitized_record[key] = float(value)
                    except (ValueError, TypeError):
                        sanitized_record[key] = value
                else:
                    sanitized_record[key] = value

        sanitized.append(sanitized_record)

    if filtered_fields > 0 and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Filtered {filtered_fields} fields from {total_fields} total")

    return sanitized


def build_upsert_statement(
    model_class,
    records: list[dict[str, Any]],
    pk: tuple[str, ...],
    db_cols: set[str] | None = None,
) -> Any:
    if not records:
        raise ValueError("No records provided for UPSERT")

    first_record = records[0]
    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Building UPSERT for {len(records)} records")
        logger.debug(f"First record keys: {list(first_record.keys())}")

    table_columns = db_cols if db_cols is not None else set(model_class.columns.keys())
    filtered_records = [
        {k: v for k, v in record.items() if k in table_columns} for record in records
    ]

    if filtered_records:
        removed_cols = set(first_record.keys()) - table_columns
        if removed_cols and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
            logger.warning(f"Filtered out {len(removed_cols)} columns not in table")

    records = filtered_records
    if not records:
        raise ValueError("No valid records after filtering by table columns")

    first_record = records[0]
    normalized_records: list[dict[str, Any]] = []
    psar_types: set[str] = set()

    for record in records:
        normalized_record: dict[str, Any] = {}
        for key, value in record.items():
            if key == "psar":
                psar_types.add(type(value).__name__)

            if value is None or pd.isna(value):
                normalized_record[key] = None
            elif isinstance(value, pd.Series | pd.DataFrame):
                if len(value) == 0:
                    normalized_record[key] = None
                else:
                    try:
                        scalar_value = (
                            value.iloc[0]
                            if isinstance(value, pd.Series)
                            else value.iloc[0, 0]
                        )
                        normalized_record[key] = (
                            None
                            if pd.isna(scalar_value)
                            else _normalize_value(scalar_value)
                        )
                    except Exception:
                        normalized_record[key] = None
            elif isinstance(value, np.ndarray):
                if value.size == 0:
                    normalized_record[key] = None
                else:
                    try:
                        normalized_record[key] = _normalize_value(value.flat[0])
                    except Exception:
                        normalized_record[key] = None
            else:
                normalized_record[key] = _normalize_value(value)
        normalized_records.append(normalized_record)

    if psar_types and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        psar_normalized_types = set()
        for record in normalized_records:
            if "psar" in record:
                psar_normalized_types.add(type(record["psar"]).__name__)
        logger.debug(f"psar types: {psar_types} -> {psar_normalized_types}")

    if normalized_records:
        all_keys: set[str] = set()
        for record in normalized_records:
            all_keys.update(record.keys())
        for record in normalized_records:
            for key in all_keys:
                if key not in record:
                    record[key] = None

    if normalized_records:
        numeric_column_names = get_numeric_columns(model_class)
        if numeric_column_names and should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.debug(f"Normalizing {len(numeric_column_names)} numeric columns")

            column_types: dict[str, Any] = {}
            if hasattr(model_class, "columns"):
                for col_name, col in model_class.columns.items():
                    if col_name in numeric_column_names:
                        column_types[col_name] = col.type
            elif hasattr(model_class, "__table__"):
                for col_name, col in model_class.__table__.columns.items():
                    if col_name in numeric_column_names:
                        column_types[col_name] = col.type

            problematic_values: dict[str, list[tuple[Any, type]]] = {}
            for record in normalized_records:
                for key in numeric_column_names:
                    if key in record:
                        value = record[key]
                        if value is not None and isinstance(value, str):
                            problematic_values.setdefault(key, []).append(
                                (value, type(value))
                            )

            if problematic_values and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
                for key, samples in list(problematic_values.items())[:3]:
                    logger.warning(
                        f"String values in numeric column '{key}': {len(samples)} found"
                    )

            for record in normalized_records:
                for key in numeric_column_names:
                    if key not in record:
                        continue

                    value = record[key]
                    if value is None:
                        continue

                    col_type = column_types.get(key)
                    has_precision_scale = (
                        col_type
                        and hasattr(col_type, "precision")
                        and hasattr(col_type, "scale")
                        and col_type.precision is not None
                        and col_type.scale is not None
                    )
                    if isinstance(value, str):
                        try:
                            is_integer = False
                            if col_type:
                                if isinstance(col_type, Integer | BigInteger):
                                    is_integer = True
                                else:
                                    type_str = str(col_type).upper()
                                    if (
                                        "INTEGER" in type_str
                                        or "BIGINT" in type_str
                                        or "SMALLINT" in type_str
                                    ):
                                        is_integer = True

                                if has_precision_scale and isinstance(
                                    col_type, Numeric
                                ):
                                    clipped = _clip_numeric_value(
                                        float(value),
                                        col_type.precision,
                                        col_type.scale,
                                    )
                                    normalized = int(clipped) if is_integer else clipped
                                else:
                                    normalized = (
                                        int(float(value))
                                        if is_integer
                                        else float(value)
                                    )
                            else:
                                normalized = float(value)
                            record[key] = normalized
                        except (ValueError, TypeError):
                            record[key] = None
                    elif value is not None and not isinstance(
                        value, int | float | np.number
                    ):
                        try:
                            normalized: float = float(value)
                            if has_precision_scale and isinstance(col_type, Numeric):
                                normalized = _clip_numeric_value(
                                    normalized, col_type.precision, col_type.scale
                                )
                            record[key] = normalized
                        except (ValueError, TypeError):
                            record[key] = None
                    elif isinstance(value, np.number):
                        normalized: float | int = float(value)
                        if has_precision_scale and isinstance(col_type, Numeric):
                            normalized = _clip_numeric_value(
                                normalized, col_type.precision, col_type.scale
                            )
                        record[key] = normalized

    stmt = pg_insert(model_class).values(normalized_records)
    update_dict = {}
    non_pk_fields = [k for k in first_record if k not in pk]

    skipped_fields = []
    for field in non_pk_fields:
        try:
            update_dict[field] = stmt.excluded[field]
        except (KeyError, AttributeError):
            skipped_fields.append(field)
            continue
        except Exception as e:
            logger.error(f"Unexpected error with field '{field}': {e}")
            continue

    if skipped_fields and should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"Skipped {len(skipped_fields)} fields not in excluded")

    if not update_dict:
        raise ValueError("No fields available for UPSERT update")

    stmt = stmt.on_conflict_do_update(index_elements=list(pk), set_=update_dict)

    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        logger.debug(f"UPSERT statement built with {len(update_dict)} update fields")

    return stmt


async def execute_upsert(
    session: AsyncSession, stmt: Any, records: list[dict[str, Any]]
) -> int:
    if should_log(LogCategory.DIAG, Verbosity.DEBUG) and records:
        num_cols = len(records[0])
        total_params = len(records) * num_cols
        logger.debug(
            f"Executing UPSERT: {len(records)} rows x {num_cols} cols = {total_params} params"
        )

    try:
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            try:
                compiled = stmt.compile(compile_kwargs={"literal_binds": False})
                sql_str = str(compiled)
                sql_preview = sql_str[:300] if len(sql_str) > 300 else sql_str
                logger.debug(f"SQL preview: {sql_preview}...")
            except Exception:
                pass

        result = await session.execute(stmt)
        if should_log(LogCategory.DIAG, Verbosity.DEBUG) and hasattr(
            result, "rowcount"
        ):
            logger.debug(f"Affected rows: {result.rowcount}")
        return len(records)
    except Exception as e:
        import traceback

        logger.error(f"UPSERT FAILED: {type(e).__name__}: {e}")
        logger.error(f"Records count: {len(records)}")
        if records:
            logger.error(f"First record keys: {list(records[0].keys())[:15]}...")
            logger.error(f"First record sample: {dict(list(records[0].items())[:5])}")

        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.error(f"Full traceback:\n{traceback.format_exc()}")

        raise


async def build_and_execute_upsert(
    session: AsyncSession,
    model_class,
    records: list[dict[str, Any]],
    db_cols: set[str],
    pk: tuple[str, ...] = IndicatorStorageContract.identity_fields,
    required_fields: set[str] | None = None,
) -> int:
    with LogAggregator(LogCategory.INSERT, "upsert") as agg:
        if required_fields is None:
            required_fields = IndicatorStorageContract.required_fields_set()
        validate_upsert_data(records, db_cols, required_fields)

        sanitized_records = sanitize_records(records, db_cols)
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.debug(
                f"prepared {len(records)} records, sanitized {len(sanitized_records)}"
            )

        if not sanitized_records:
            logger.warning("No valid records after sanitization")
            return 0

        filtered_records = filter_problematic_fields(sanitized_records)
        if not filtered_records:
            logger.warning("No valid records after filtering")
            return 0

        numeric_columns = get_numeric_columns(model_class)
        try:
            validate_numeric_types(filtered_records, numeric_columns, row_offset=0)
        except (TypeError, ValueError) as validation_error:
            logger.error(f"Type validation failed: {validation_error}")
            raise

        if filtered_records:
            num_fields = len(filtered_records[0])
            calculated_batch_size = _get_dynamic_batch_size(
                num_fields=num_fields,
                total_records=len(filtered_records),
            )
        else:
            calculated_batch_size = DEFAULT_MIN_BATCH_SIZE

        prom = get_prom_metrics()
        symbol_label = ""
        timeframe_label = ""
        if filtered_records:
            symbol_label = str(filtered_records[0].get("symbol", ""))
            timeframe_label = str(filtered_records[0].get("timeframe", ""))

        num_batches_total = max(
            1,
            (len(filtered_records) - 1) // calculated_batch_size + 1,
        )
        if symbol_label and timeframe_label:
            prom.record_batch_size(symbol_label, timeframe_label, calculated_batch_size)
            logger.info(
                "Batch plan: %d records, %d fields, batch_size=%d, num_batches=%d",
                len(filtered_records),
                num_fields,
                calculated_batch_size,
                num_batches_total,
            )

        total_saved = 0
        if DIAGNOSTIC_SINGLE_ROW:
            logger.warning(
                f"DIAGNOSTIC_SINGLE_ROW: Processing {len(filtered_records)} records individually"
            )

            for i, rec in enumerate(filtered_records):
                try:
                    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                        logger.debug(
                            f"Processing record {i + 1}/{len(filtered_records)}"
                        )
                    validate_numeric_types([rec], numeric_columns, row_offset=i)
                    stmt = build_upsert_statement(model_class, [rec], pk, db_cols)
                    batch_saved = await execute_upsert(session, stmt, [rec])
                    total_saved += batch_saved
                except Exception:
                    logger.error(f"UPSERT FAILED on record {i + 1}")
                    logger.error(f"Record sample: {dict(list(rec.items())[:10])}")
                    raise

            agg.set_extra("mode", "diagnostic")
            agg.set_extra("saved", total_saved)
            return total_saved

        if len(filtered_records) > calculated_batch_size:
            num_batches = (len(filtered_records) - 1) // calculated_batch_size + 1

            if should_log(LogCategory.DIAG, Verbosity.VERBOSE):
                logger.info(
                    f"Splitting {len(filtered_records)} records into {num_batches} batches"
                )

            for i in range(0, len(filtered_records), calculated_batch_size):
                batch = filtered_records[i : i + calculated_batch_size]
                batch_num = i // calculated_batch_size + 1

                if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                    logger.debug(
                        f"Processing batch {batch_num}/{num_batches} ({len(batch)} records)"
                    )

                try:
                    validate_numeric_types(batch, numeric_columns, row_offset=i)
                except (TypeError, ValueError) as batch_validation_error:
                    logger.error(
                        f"Type validation failed for batch {batch_num}: {batch_validation_error}"
                    )
                    raise

                try:
                    stmt = build_upsert_statement(model_class, batch, pk, db_cols)
                    batch_saved = await execute_upsert(session, stmt, batch)
                    total_saved += batch_saved
                    agg.add("batches", value=len(batch))
                except Exception as batch_error:
                    logger.error(f"UPSERT failed for batch {batch_num}: {batch_error}")
                    raise

            agg.set_extra("saved", total_saved)
            agg.set_extra("batches_count", num_batches)
            return total_saved

        stmt = build_upsert_statement(model_class, filtered_records, pk, db_cols)
        result = await execute_upsert(session, stmt, filtered_records)
        agg.set_extra("saved", result)
        return result


__all__ = [
    "_clip_numeric_value",
    "_normalize_value",
    "build_and_execute_upsert",
    "build_upsert_statement",
    "execute_upsert",
    "sanitize_records",
]
