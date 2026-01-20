"""
Merging logic for combining calculated indicator results into DataFrame.

This module handles the merging of calculated indicators from different groups
into a unified result DataFrame with proper name normalization and critical field handling.
"""

import logging
import os

import numpy as np
import pandas as pd

from ..name_mapping import normalize_indicator_name

logger = logging.getLogger(__name__)

# Кэш для нормализации имён индикаторов (оптимизация производительности)
_normalize_cache: dict[str, str] = {}

# Кэш для проверки типов полей (оптимизация производительности)
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
    logger.debug(
        f"Total result keys count={len(result)} keys_sample={list(result.keys())[:10]}"
    )

    # Debug: check result after all updates
    logger.debug("Result after all updates:")
    for key, value in result.items():
        if isinstance(value, pd.Series):
            non_null = value.notna().sum()
            logger.debug(f"  {key}: {non_null}/{len(value)} non-null")
        else:
            logger.debug(f"  {key}: {type(value)} - {value}")

    # Add calculated indicators to result DataFrame with name normalization
    logger.debug(
        f"Starting merge loop items_count={len(result)} keys_sample={list(result.keys())[:10]} result_type={type(result)!s}"
    )

    # Process each indicator
    processed_count = 0
    # Диагностика overlap индикаторов
    overlap_diagnostic = ["hlc3", "hl2", "ohlc4", "wcp"]
    logger.info(
        f"DIAGNOSTIC: Processing {len(result)} indicators, checking overlap: {overlap_diagnostic}"
    )
    logger.info(
        f"DIAGNOSTIC: available_names contains overlap: {[n for n in overlap_diagnostic if n in available_names]}"
    )

    # Собираем новые колонки в словарь для избежания фрагментации
    new_columns: dict[str, pd.Series] = {}

    # Диагностика: проверяем наличие критических полей в result
    critical_in_result = ["ichimoku_chikou", "t3_20", "rma_20"]
    for crit_name in critical_in_result:
        if crit_name in result:
            crit_value = result[crit_name]
            if isinstance(crit_value, pd.Series):
                logger.info(
                    f"✅ Critical field {crit_name} found in result: {crit_value.notna().sum()}/{len(crit_value)} non-null"
                )
            else:
                logger.info(
                    f"✅ Critical field {crit_name} found in result: {type(crit_value)}"
                )
        else:
            logger.warning(
                f"❌ Critical field {crit_name} NOT found in result dictionary"
            )

    for name, values in result.items():
        processed_count += 1
        logger.debug(f"Processing item {processed_count}/{len(result)} name={name}")
        try:
            target_name = _normalize_indicator_name_for_merge(name, available_names)
            is_critical, is_overlap = _check_field_types(target_name, [])
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
        except Exception as e:
            logger.error(
                f"Error processing {name}: {e}",
                exc_info=True,
                extra={"indicator_name": name},
            )
            continue

    # Применяем все новые колонки одним concat для избежания фрагментации
    if new_columns:
        result_df = _apply_new_columns(result_df, new_columns)

    logger.debug(f"Merge loop completed processed_count={processed_count}")
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
    # Кэширование нормализации имён для оптимизации производительности
    if name not in _normalize_cache:
        _normalize_cache[name] = normalize_indicator_name(name)
    target_name = _normalize_cache[name]
    # Специальная обработка для ichimoku_chikou -> ics_26
    if name == "ichimoku_chikou":
        if "ics_26" in available_names:
            target_name = "ics_26"
            logger.info(
                "Mapping ichimoku_chikou -> ics_26 (available_names contains ics_26)"
            )
        elif "ichimoku_chikou" in available_names:
            target_name = "ichimoku_chikou"
            logger.info("Keeping ichimoku_chikou as is (ics_26 not in available_names)")
        else:
            target_name = "ics_26"
            logger.info(
                "Mapping ichimoku_chikou -> ics_26 (forcing, neither in available_names)"
            )
    return target_name


def _check_field_types(
    target_name: str, overlap_diagnostic: list[str]
) -> tuple[bool, bool]:
    """
    Check if field is critical or overlap.

    Args:
        target_name: Target indicator name
        overlap_diagnostic: List of overlap indicator names (для совместимости, не используется)

    Returns:
        Tuple of (is_critical, is_overlap)
    """
    # Оптимизация: используем frozenset для быстрой проверки
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
    # Используем кэшированный frozenset вместо создания списка каждый раз
    should_process = (
        len(available_names) == 0
        or target_name in available_names
        or (is_overlap and isinstance(values, pd.Series) and values.notna().sum() > 0)
        or (is_critical and isinstance(values, pd.Series) and values.notna().sum() > 0)
    )

    # КРИТИЧНО: overlap индикаторы должны быть в result_df всегда, если рассчитаны
    if is_overlap and isinstance(values, pd.Series) and values.notna().sum() > 0:
        should_process = True

    # КРИТИЧНО: критические поля должны быть в result_df всегда, если рассчитаны
    if is_critical and isinstance(values, pd.Series) and values.notna().sum() > 0:
        should_process = True
        logger.info(
            f"✅ Processing critical field {target_name}: {values.notna().sum()}/{len(values)} non-null"
        )
    elif is_critical:
        # Даже если все значения NaN, всё равно обрабатываем критические поля
        should_process = True
        logger.warning(f"⚠️ Processing critical field {target_name} with all NaN values")

    # Диагностика для overlap индикаторов
    if is_overlap:
        logger.info(
            f"DIAGNOSTIC: {target_name}, should_process={should_process}, in available={target_name in available_names}, is_overlap={is_overlap}"
        )
        if isinstance(values, pd.Series):
            logger.info(
                f"DIAGNOSTIC: {target_name} non-null: {values.notna().sum()}/{len(values)}"
            )

    logger.debug(
        f"Name mapping target={target_name} should_process={should_process} available_count={len(available_names)}"
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
    # Debug log for merge process
    if os.getenv("FEATURES_VERBOSE", "false").lower() == "true":
        if isinstance(values, pd.Series):
            non_null_count = values.notna().sum()
            logger.debug(
                f"MERGE: -> {target_name} non_null={non_null_count}/{len(values)}"
            )
        else:
            logger.debug(f"MERGE: -> {target_name} value_type=non-Series")

    # Debug: check values before processing
    logger.debug(f"{target_name} values type value_type={type(values)!s}")
    if isinstance(values, pd.Series):
        logger.debug(
            f"{target_name} values quality non_null={values.notna().sum()}/{len(values)}"
        )
        logger.debug(f"{target_name} values sample head={values.head(2).tolist()}")
        logger.debug(
            f"{target_name} index info values_index={values.index!s} result_index={result_index!s}"
        )

    # Merge strategy: never overwrite a more-complete column with a worse one
    # Build aligned series: always reindex to result_df.index for safety
    if isinstance(values, pd.DataFrame):
        if values.shape[1] == 1:
            values = values.iloc[:, 0]
        else:
            logger.warning(
                f"DataFrame with {values.shape[1]} columns for {target_name}, taking first column"
            )
            values = values.iloc[:, 0]

    if isinstance(values, pd.Series):
        # Оптимизация: проверяем совпадение индекса перед reindex
        if values.index.equals(result_index):
            # Индекс уже совпадает - используем копию без reindex
            new_series = values.copy()
        else:
            # Нормализуем индекс через reindex для гарантии совпадения
            new_series = values.reindex(result_index, fill_value=np.nan)
        new_series.name = target_name
        # Гарантируем float64 dtype
        if new_series.dtype == "object":
            new_series = pd.to_numeric(new_series, errors="coerce")
        new_series = new_series.astype("float64")
    else:
        # Fallback для не-Series значений
        new_series = pd.Series(
            values, index=result_index, name=target_name, dtype="float64"
        )

    # Валидация: проверяем что new_series не пустой и имеет правильный индекс
    # Оптимизация: убрали избыточный reindex, так как индекс уже проверен выше
    if len(new_series) != len(result_index):
        logger.warning(
            f"Длина {target_name} не совпадает с result_df: {len(new_series)} != {len(result_index)}"
        )
        # Принудительно выравниваем по индексу (только если действительно не совпадает)
        if not new_series.index.equals(result_index):
            new_series = new_series.reindex(result_index, fill_value=np.nan)

    # Debug: log before adding to result_df
    logger.info(
        f"Adding {target_name} to result_df: {new_series.notna().sum()}/{len(new_series)} non-null"
    )

    if os.getenv("FEATURES_VERBOSE", "false").lower() == "true":
        if isinstance(new_series, pd.Series):
            total = len(new_series)
            non_null = int(new_series.notna().sum())
            pct = (non_null / total * 100) if total else 0.0
            logger.debug(
                f"FEATURE READY {target_name}: filled {non_null}/{total} ({pct:.1f}%)"
            )

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
    # Сохраняем в словарь вместо прямого присваивания
    # Критические поля всегда добавляем, даже если все значения NaN
    if is_critical:
        new_columns[target_name] = new_series
        logger.info(
            f"✅ Critical field {target_name} added to new_columns (even with NaN values)"
        )
    elif target_name in result_df.columns:
        cur = result_df[target_name]
        cur_non_null = int(cur.notna().sum())
        new_non_null = int(new_series.notna().sum())
        logger.info(f"{target_name} exists: cur={cur_non_null}, new={new_non_null}")
        if new_non_null > cur_non_null:
            new_columns[target_name] = new_series
            logger.info(f"{target_name} updated with new data")
        else:
            logger.info(f"{target_name} kept existing data (cur better)")
    else:
        new_columns[target_name] = new_series
        logger.info(f"{target_name} added as new column")


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
    logger.info(
        f"Applying {len(new_columns)} new columns via concat to avoid fragmentation"
    )
    # Проверяем наличие критических полей в new_columns перед concat
    critical_in_new = [
        "ics_26",
        "t3_20",
        "rma_20",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "hlc3",
        "hl2",
        "ohlc4",
    ]
    for crit_field in critical_in_new:
        if crit_field in new_columns:
            logger.info(f"✅ Critical field {crit_field} in new_columns before concat")
        else:
            logger.warning(
                f"❌ Critical field {crit_field} NOT in new_columns before concat"
            )

    # Приводим типы к Float64 для числовых колонок перед concat
    # Это устраняет FutureWarning о несовместимых типах
    # Векторизация: обрабатываем все числовые серии одновременно
    numeric_columns = {
        col_name: series.astype("Float64")
        for col_name, series in new_columns.items()
        if pd.api.types.is_numeric_dtype(series)
    }
    new_columns.update(numeric_columns)
    # Создаём DataFrame из новых колонок
    new_df = pd.DataFrame(new_columns, index=result_df.index)
    # Объединяем с существующим DataFrame
    result_df = pd.concat([result_df, new_df], axis=1)
    # Удаляем дубликаты колонок (если были обновления)
    result_df = result_df.loc[:, ~result_df.columns.duplicated(keep="last")]
    # Проверяем наличие критических полей в result_df после concat
    for crit_field in critical_in_new:
        if crit_field in result_df.columns:
            non_null = result_df[crit_field].notna().sum()
            logger.info(
                f"✅ Critical field {crit_field} in result_df after concat: {non_null}/{len(result_df)} non-null"
            )
        else:
            logger.warning(
                f"❌ Critical field {crit_field} NOT in result_df after concat"
            )

    return result_df
