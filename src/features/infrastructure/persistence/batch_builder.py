"""
Batch building functions for indicator data.

Phase 2.1: Added DIP compliance with optional validator injection.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from src.logging import get_logger

from ...schema.name_aliases import CRITICAL_ALWAYS_SAVE

logger = get_logger(__name__)


@runtime_checkable
class TimestampValidatorProtocol(Protocol):
    """Protocol for timestamp validation (DIP compliance)."""

    def __call__(self, timestamp: int | None, row_index: int | str) -> bool:
        """Validate a timestamp value."""
        ...


def build_batch_data(
    ind_df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    db_cols: set[str],
    timestamp_validator: TimestampValidatorProtocol | None = None,
    seen_timestamps: set[int] | None = None,
    on_duplicate: Callable[[str, str, int], None] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Build batch data from DataFrame for database insertion.

    This function follows the Dependency Inversion Principle (DIP):
    It accepts an optional validator implementing TimestampValidatorProtocol.

    Args:
        ind_df: DataFrame with indicator data
        symbol: Symbol value
        timeframe: Timeframe value
        db_cols: Set of database column names
        timestamp_validator: Optional custom timestamp validator.
                            If None, uses the default validate_timestamp.
        seen_timestamps: Optional shared set of seen timestamps.
            Pass the same set across chunks to detect boundary duplicates.
        on_duplicate: Optional callback called as
            on_duplicate(symbol, timeframe, duplicate_rows).

    Returns:
        Tuple of (batch_data list, skipped_rows count)
    """
    # Use injected validator or default (DIP compliance)
    if timestamp_validator is None:
        from .validator import validate_timestamp
        timestamp_validator = validate_timestamp

    batch_data: list[dict[str, Any]] = []
    skipped_rows = 0
    duplicate_rows = 0
    if seen_timestamps is None:
        seen_timestamps = set()

    # Используем itertuples() для лучшей производительности (быстрее iterrows())
    # itertuples() возвращает namedtuple с атрибутами, соответствующими колонкам
    # index=True включает индекс в кортеж как первый элемент
    for row_tuple in ind_df.itertuples(index=True, name=None):
        try:
            # row_tuple[0] - индекс, row_tuple[1:] - значения колонок
            idx = row_tuple[0]
            # Создаём словарь для доступа к значениям по имени колонки
            # Используем enumerate для сопоставления индекса колонки с именем
            row_dict = {col: row_tuple[i + 1] for i, col in enumerate(ind_df.columns)}

            # ВАЛИДАЦИЯ: timestamp уже нормализован на уровне DataFrame
            timestamp_ms = row_dict.get("timestamp")
            if timestamp_ms is None or not timestamp_validator(timestamp_ms, idx):
                skipped_rows += 1
                continue

            # F.2: Detect duplicate timestamps within the batch
            if timestamp_ms in seen_timestamps:
                duplicate_rows += 1
                logger.debug(
                    "Row %s: duplicate timestamp %s, skipping", idx, timestamp_ms
                )
                continue
            seen_timestamps.add(timestamp_ms)

            # Use the data timestamp for calculated_at, not current time
            # Используем naive datetime для совместимости с timestamp without time zone
            ts_sec = timestamp_ms // 1000
            calculated_at = datetime.datetime.utcfromtimestamp(ts_sec)  # naive UTC

            base_data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": timestamp_ms,
                "calculated_at": calculated_at,
            }

            # Добавляем только индикаторные столбцы (без OHLCV)
            indicator_data = {**base_data}
            indicators_added = 0

            # ШАГ 3: Безопасный доступ к значениям при сборке батча
            # Универсальная фильтрация по колонкам модели
            # Критические поля должны быть включены даже с NaN значениями
            # Используем единый список критических полей из name_aliases
            critical_fields = CRITICAL_ALWAYS_SAVE

            for col in ind_df.columns:
                if col in ("ts", "open", "high", "low", "close", "volume"):
                    continue
                if col not in db_cols:
                    if col in critical_fields:
                        logger.warning(
                            f"Column '{col}' not in db_cols but is critical, skipping. db_cols contains: {sorted(db_cols)[:10]}..."
                        )
                    continue

                # Безопасный доступ к значению
                val = row_dict.get(col)
                if val is None:
                    # Для критических полей добавляем None даже если значение отсутствует
                    is_critical = col in critical_fields
                    if is_critical:
                        indicator_data[col] = None
                        indicators_added += 1
                        logger.debug(
                            f"Row {idx}, critical field {col}: Adding with None (missing value)"
                        )
                    continue

                # Для критических полей добавляем даже NaN значения (как None)
                is_critical = col in critical_fields
                if isinstance(val, float) and (np.isnan(val) or np.isinf(val)):
                    if is_critical:
                        # Для критических полей используем None вместо пропуска
                        indicator_data[col] = None
                        indicators_added += 1
                        logger.debug(
                            f"Row {idx}, critical field {col}: Adding with NaN (as None)"
                        )
                    else:
                        # Для некритических полей пропускаем NaN
                        continue

                try:
                    float_val = float(val)
                    if np.isnan(float_val) or np.isinf(float_val):
                        if is_critical:
                            # Для критических полей используем None вместо пропуска
                            indicator_data[col] = None
                            indicators_added += 1
                            logger.debug(
                                f"Row {idx}, critical field {col}: Adding with NaN (as None)"
                            )
                        else:
                            # Для некритических полей пропускаем NaN
                            continue
                    else:
                        indicator_data[col] = float_val
                        indicators_added += 1
                except (ValueError, TypeError, OverflowError) as e:
                    if is_critical:
                        # Для критических полей используем None при ошибке
                        indicator_data[col] = None
                        indicators_added += 1
                        logger.debug(
                            f"Row {idx}, critical field {col}: Invalid value {val}, using None: {e}"
                        )
                    else:
                        logger.debug(
                            f"Row {idx}, column {col}: Invalid value {val}: {e}"
                        )
                        continue

            # Даже если все индикаторы NaN (прогрев окон) - сохраняем строку,
            # чтобы не терять свечу в БД
            if indicators_added == 0:
                logger.debug(
                    "Row %s: только базовые поля, вставляем без рассчитанных индикаторов",
                    idx,
                )
            batch_data.append(indicator_data)

        except Exception as e:
            logger.error(
                f"Row {idx if 'idx' in locals() else 'unknown'}: Error processing row: {e}",
                exc_info=True,
                extra={
                    "row_index": str(idx) if "idx" in locals() else "unknown",
                    "symbol": symbol,
                    "timeframe": timeframe,
                },
            )
            skipped_rows += 1
            continue

    if duplicate_rows > 0 and on_duplicate:
        on_duplicate(symbol, timeframe, duplicate_rows)
        logger.warning(
            "Detected %d duplicate timestamps in batch for %s/%s",
            duplicate_rows,
            symbol,
            timeframe,
        )

    logger.info(
        "Prepared %d records for insertion, skipped %d rows (duplicates: %d)",
        len(batch_data),
        skipped_rows,
        duplicate_rows,
    )
    return batch_data, skipped_rows


def filter_batch_by_schema(
    batch_data: list[dict[str, Any]], db_cols: set[str], base_keys: list[str]
) -> list[dict[str, Any]]:
    """
    Filter batch data to match database schema.

    Args:
        batch_data: List of records to filter
        db_cols: Set of database column names
        base_keys: List of base keys that must be preserved

    Returns:
        Filtered batch data

    Raises:
        ValueError: If base keys are missing after filtering
    """
    from .validator import validate_record_base_keys

    safe_batch_data = []
    allowed_cols = db_cols  # db_cols уже содержит все нужные колонки включая base_keys

    # Логируем статистику фильтрации
    total_fields = 0
    filtered_fields = 0

    for record in batch_data:
        # Проверяем наличие базовых ключей перед фильтрацией
        try:
            validate_record_base_keys(record, base_keys)
        except ValueError:
            logger.warning("Record missing base keys, skipping")
            logger.debug(f"Record keys: {list(record.keys())}")
            continue

        # Подсчитываем поля для статистики
        total_fields += len(record)

        safe_record = {k: v for k, v in record.items() if k in allowed_cols}
        filtered_fields += len(record) - len(safe_record)

        safe_batch_data.append(safe_record)

    if filtered_fields > 0:
        logger.info(
            f"Filtered out {filtered_fields} fields from {total_fields} total fields (not in DB schema)"
        )

    # Проверяем, что базовые ключи сохранились после фильтрации
    if safe_batch_data:
        first_record = safe_batch_data[0]
        missing_after_filter = [k for k in base_keys if k not in first_record]
        if missing_after_filter:
            logger.error(f"Base keys missing after filtering: {missing_after_filter}")
            logger.error(f"Available keys after filtering: {list(first_record.keys())}")
            raise ValueError(
                f"Base keys missing after filtering: {missing_after_filter}"
            )

        # Дополнительная проверка: убеждаемся, что все записи имеют базовые ключи
        for i, record in enumerate(safe_batch_data):
            missing_in_record = [k for k in base_keys if k not in record]
            if missing_in_record:
                logger.error(f"Record {i} missing base keys: {missing_in_record}")
                logger.error(f"Record {i} keys: {list(record.keys())}")
                raise ValueError(f"Record {i} missing base keys: {missing_in_record}")

        logger.info(
            f"✅ All {len(safe_batch_data)} records have required base keys: {base_keys}"
        )

    return safe_batch_data


def normalize_record_names(
    batch_data: list[dict[str, Any]], db_cols: set[str]
) -> list[dict[str, Any]]:
    """
    Normalize record field names using name mapping.

    Args:
        batch_data: List of records to normalize
        db_cols: Set of database column names

    Returns:
        Normalized batch data

    Raises:
        ValueError: If no valid fields remain after filtering
    """
    # НОРМАЛИЗАЦИЯ ИМЁН: Приводим к единому канону ДО фильтрации
    name_mapping = {
        "ema12": "ema_12",
        "ema21": "ema_21",
        "ema26": "ema_26",
        "ema50": "ema_50",
        "ema200": "ema_200",
        "sma200": "sma_200",
        "sma34": "sma_34",
        "sma50": "sma_50",
        "cci_14": "cci_14",  # Уже правильное имя
        "mfi_14": "mfi_14",  # Уже правильное имя
    }

    pk = {"symbol", "timeframe", "timestamp"}

    # Создаём отфильтрованный и нормализованный батч данных
    filtered_batch = []
    for record in batch_data:
        # Нормализуем имена полей
        normalized_record = {}
        for k, v in record.items():
            # Применяем маппинг имён
            normalized_key = name_mapping.get(k, k)
            # Базовые ключи всегда проходят независимо от db_cols
            if normalized_key in db_cols or normalized_key in pk:
                normalized_record[normalized_key] = v
            else:
                logger.debug(
                    f"Filtering out field '{k}' -> '{normalized_key}' (not in DB schema)"
                )

        filtered_batch.append(normalized_record)

    if not filtered_batch:
        logger.error("CRITICAL: No valid fields after filtering by DB schema!")
        logger.error(
            f"Original batch keys: {list(batch_data[0].keys()) if batch_data else 'empty'}"
        )
        logger.error(f"DB schema columns: {sorted(db_cols)}")
        raise ValueError("No valid fields after schema filtering")

    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Жёсткая фильтрация payload по реальным колонкам БД
    safe_batch_data = []
    for record in filtered_batch:
        safe_record = {k: v for k, v in record.items() if k in db_cols}
        safe_batch_data.append(safe_record)

    # Проверяем, что есть данные для вставки
    if not safe_batch_data:
        logger.error("CRITICAL: No safe data after filtering!")
        logger.error(f"Original batch size: {len(batch_data)}")
        logger.error(f"DB schema columns: {sorted(db_cols)}")
        raise ValueError("No safe data for insertion")

    return safe_batch_data
