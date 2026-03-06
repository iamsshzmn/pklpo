"""
Merging logic for combining calculated indicator results into DataFrame.

This module handles the merging of calculated indicators from different groups
into a unified result DataFrame with proper name normalization and critical field handling.
"""

import numpy as np
import pandas as pd

from src.logging import (
    LogAggregator,
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)

from ..schema.name_aliases import normalize_name

logger = get_category_logger(LogCategory.MERGE)

#      ( )
_normalize_cache: dict[str, str] = {}

#      ( )
_CRITICAL_FIELDS = frozenset(["ics_26", "t3_20", "rma_20", "hlc3", "ohlc4", "hl2"])
_OVERLAP_DIAGNOSTIC = frozenset(["hlc3", "hl2", "ohlc4", "wcp"])


def merge_indicator_results(
    result: dict[str, pd.Series | pd.DataFrame | object],
    result_df: pd.DataFrame,
    available_names: set[str],
) -> pd.DataFrame:
    """
    Merge calculated indicator results into result DataFrame.

    Args:
        result: Dictionary of calculated indicators (name -> Series/DataFrame)
        result_df: Base DataFrame to merge into
        available_names: Set of available indicator names for filtering

    Returns:
        DataFrame with merged indicator columns
    """
    # Use aggregator for summary logging instead of per-indicator logs
    with LogAggregator(LogCategory.MERGE, "merge_indicators") as agg:
        # DEBUG: detailed diagnostics
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.debug(
                f"Total result keys count={len(result)} keys_sample={list(result.keys())[:10]}"
            )
            for key, value in result.items():
                if isinstance(value, pd.Series):
                    non_null = value.notna().sum()
                    logger.debug(f"  {key}: {non_null}/{len(value)} non-null")

        # Collect new columns first to avoid frame fragmentation.
        new_columns: dict[str, pd.Series] = {}

        # Track metrics for aggregated logging
        critical_found = 0
        critical_missing = 0
        overlap_count = 0
        errors = 0

        # Check critical fields (only log at DEBUG level)
        critical_in_result = ["ichimoku_chikou", *list(_CRITICAL_FIELDS)]
        for crit_name in critical_in_result:
            if crit_name in result:
                critical_found += 1
            else:
                critical_missing += 1
                if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                    logger.debug(f"Critical field {crit_name} not in result")

        for name, values in result.items():
            try:
                target_name = _normalize_indicator_name_for_merge(name, available_names)
                is_critical, is_overlap = _check_field_types(target_name, [])

                if is_overlap:
                    overlap_count += 1

                should_process = _should_process_indicator(
                    target_name, values, available_names, is_critical, is_overlap
                )

                if should_process:
                    new_series = _prepare_series_for_merge(
                        values, target_name, result_df.index
                    )
                    if new_series is not None:
                        _add_to_new_columns(
                            new_columns, new_series, target_name, result_df, is_critical
                        )
                        # Track fill rate for aggregation
                        if isinstance(new_series, pd.Series) and len(new_series) > 0:
                            fill_rate = new_series.notna().sum() / len(new_series)
                            agg.add("columns", target_name, value=fill_rate)
            except Exception as e:
                errors += 1
                agg.add_error(f"Error processing {name}: {e}")
                if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                    logger.debug(f"Error processing {name}: {e}", exc_info=True)
                continue

        #      concat
        if new_columns:
            result_df = _apply_new_columns(result_df, new_columns)

        # Set aggregator extra info
        agg.set_extra("total", len(result))
        agg.set_extra("added", len(new_columns))
        if critical_missing > 0:
            agg.set_extra("critical_missing", critical_missing)
        if overlap_count > 0:
            agg.set_extra("overlap", overlap_count)
        if errors > 0:
            agg.set_extra("errors", errors)

    return result_df


def _normalize_indicator_name_for_merge(name: str, available_names: set[str]) -> str:
    """
    Normalize indicator name for merging.

    Args:
        name: Original indicator name
        available_names: Set of available indicator names

    Returns:
        Normalized target name
    """
    # Cache normalized names to avoid repeated work.
    if name not in _normalize_cache:
        _normalize_cache[name] = normalize_name(name)
    target_name = _normalize_cache[name]
    # Special handling for ichimoku_chikou -> ics_26.
    if name == "ichimoku_chikou":
        if "ics_26" in available_names:
            target_name = "ics_26"
        elif "ichimoku_chikou" in available_names:
            target_name = "ichimoku_chikou"
        else:
            target_name = "ics_26"
        # Log only at DEBUG level
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            logger.debug(f"Mapping ichimoku_chikou -> {target_name}")
    return target_name


def _check_field_types(
    target_name: str, overlap_diagnostic: list[str]
) -> tuple[bool, bool]:
    """
    Check if field is critical or overlap.

    Args:
        target_name: Target indicator name
        overlap_diagnostic: Legacy overlap indicator names, kept for compatibility

    Returns:
        Tuple of (is_critical, is_overlap)
    """
    # Use frozenset membership for fast checks.
    is_critical = target_name in _CRITICAL_FIELDS
    is_overlap = target_name in _OVERLAP_DIAGNOSTIC
    return is_critical, is_overlap


def _should_process_indicator(
    target_name: str,
    values: pd.Series | pd.DataFrame | object,
    available_names: set[str],
    is_critical: bool,
    is_overlap: bool,
) -> bool:
    """
    Determine if indicator should be processed.

    Args:
        target_name: Target indicator name
        values: Indicator values
        available_names: Set of available indicator names
        is_critical: Whether field is critical
        is_overlap: Whether field is overlap

    Returns:
        True if indicator should be processed
    """
    # Use the cached frozenset instead of rebuilding a list each time.
    should_process = (
        len(available_names) == 0
        or target_name in available_names
        or (is_overlap and isinstance(values, pd.Series) and values.notna().sum() > 0)
        or (is_critical and isinstance(values, pd.Series) and values.notna().sum() > 0)
    )

    # Overlap indicators must always be kept when they contain data.
    if is_overlap and isinstance(values, pd.Series) and values.notna().sum() > 0:
        should_process = True

    # Critical indicators must always be kept when they are calculated.
    if is_critical and isinstance(values, pd.Series) and values.notna().sum() > 0:
        should_process = True
    elif is_critical:
        # Even all-NaN critical columns should still be preserved.
        should_process = True

    # Diagnostics only at DEBUG level
    if (
        should_log(LogCategory.DIAG, Verbosity.DEBUG)
        and is_overlap
        and isinstance(values, pd.Series)
    ):
        logger.debug(
            f"overlap {target_name}: should_process={should_process}, "
            f"non_null={values.notna().sum()}/{len(values)}"
        )

    return should_process


def _prepare_series_for_merge(
    values: pd.Series | pd.DataFrame | object,
    target_name: str,
    result_index: pd.Index,
) -> pd.Series | None:
    """
    Prepare Series for merging into result DataFrame.

    Args:
        values: Indicator values (Series, DataFrame, or other)
        target_name: Target column name
        result_index: Index of result DataFrame

    Returns:
        Prepared Series or None if processing failed
    """
    # Merge strategy: never overwrite a more-complete column with a worse one
    # Build aligned series: always reindex to result_df.index for safety
    if isinstance(values, pd.DataFrame):
        if values.shape[1] == 1:
            values = values.iloc[:, 0]
        else:
            if should_log(LogCategory.DIAG, Verbosity.VERBOSE):
                logger.warning(
                    f"DataFrame with {values.shape[1]} columns for {target_name}, taking first"
                )
            values = values.iloc[:, 0]

    if isinstance(values, pd.Series):
        # Skip reindex when the index already matches.
        if values.index.equals(result_index):
            # The index already matches, so a copy is enough.
            new_series = values.copy()
        else:
            # Reindex to guarantee alignment with the result frame.
            new_series = values.reindex(result_index, fill_value=np.nan)
        new_series.name = target_name
        # Normalize object dtype to float64 where possible.
        if new_series.dtype == "object":
            new_series = pd.to_numeric(new_series, errors="coerce")
        new_series = new_series.astype("float64")
    else:
        # Fallback for non-Series values.
        new_series = pd.Series(
            values, index=result_index, name=target_name, dtype="float64"
        )

    # Validate output length and index alignment.
    if len(new_series) != len(result_index):
        if should_log(LogCategory.DIAG, Verbosity.VERBOSE):
            logger.warning(
                f"Length mismatch {target_name}: {len(new_series)} != {len(result_index)}"
            )
        # Force alignment only when the index truly differs.
        if not new_series.index.equals(result_index):
            new_series = new_series.reindex(result_index, fill_value=np.nan)

    # DEBUG: detailed per-indicator logging
    if should_log(LogCategory.DIAG, Verbosity.DEBUG) and isinstance(
        new_series, pd.Series
    ):
        total = len(new_series)
        non_null = int(new_series.notna().sum())
        pct = (non_null / total * 100) if total else 0.0
        logger.debug(f"{target_name}: {non_null}/{total} ({pct:.1f}%)")

    return new_series


def _add_to_new_columns(
    new_columns: dict[str, pd.Series],
    new_series: pd.Series,
    target_name: str,
    result_df: pd.DataFrame,
    is_critical: bool,
) -> None:
    """
    Add prepared series to new_columns dictionary.

    Args:
        new_columns: Dictionary to add to
        new_series: Prepared series
        target_name: Target column name
        result_df: Result DataFrame for comparison
        is_critical: Whether field is critical
    """
    # Critical fields are always added, even when they contain only NaN.
    if is_critical:
        new_columns[target_name] = new_series
    elif target_name in result_df.columns:
        cur = result_df[target_name]
        cur_non_null = int(cur.notna().sum())
        new_non_null = int(new_series.notna().sum())
        # Only update if new data is better
        if new_non_null > cur_non_null:
            new_columns[target_name] = new_series
    else:
        new_columns[target_name] = new_series


def _apply_new_columns(
    result_df: pd.DataFrame, new_columns: dict[str, pd.Series]
) -> pd.DataFrame:
    """
    Apply new columns to result DataFrame using concat.

    Args:
        result_df: Base DataFrame
        new_columns: Dictionary of new columns to add

    Returns:
        DataFrame with merged columns
    """
    # DEBUG: check critical fields before concat
    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        critical_in_new = list(_CRITICAL_FIELDS)
        missing_critical = [f for f in critical_in_new if f not in new_columns]
        if missing_critical:
            logger.debug(f"Critical fields not in new_columns: {missing_critical}")

    #    Float64     concat
    #   FutureWarning
    # :
    numeric_columns = {
        col_name: series.astype("Float64")
        for col_name, series in new_columns.items()
        if pd.api.types.is_numeric_dtype(series)
    }
    new_columns.update(numeric_columns)
    #  DataFrame
    new_df = pd.DataFrame(new_columns, index=result_df.index)
    #    DataFrame
    result_df = pd.concat([result_df, new_df], axis=1)
    #    (  )
    result_df = result_df.loc[:, ~result_df.columns.duplicated(keep="last")]

    # DEBUG: verify critical fields after concat
    if should_log(LogCategory.DIAG, Verbosity.DEBUG):
        critical_in_new = list(_CRITICAL_FIELDS)
        for crit_field in critical_in_new:
            if crit_field in result_df.columns:
                non_null = result_df[crit_field].notna().sum()
                logger.debug(f"{crit_field} after concat: {non_null}/{len(result_df)}")

    return result_df
