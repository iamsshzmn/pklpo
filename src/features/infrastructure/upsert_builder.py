"""
UPSERT Builder Module

Отвечает за построение SQLAlchemy UPSERT выражений с полной валидацией и диагностикой.
Чистые функции без побочных эффектов для тестируемости и надёжности.
"""

import logging
import math
import os
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Константа для размера батча
BATCH_SIZE = 50

# Режим диагностики: одна строка - один запрос (пункт 6 плана)
# Устанавливается через переменную окружения DIAGNOSTIC_SINGLE_ROW=1
DIAGNOSTIC_SINGLE_ROW = os.getenv("DIAGNOSTIC_SINGLE_ROW", "0").lower() in (
    "1",
    "true",
    "yes",
)


def get_numeric_columns(model_class: Any) -> set[str]:
    """
    Определяет числовые колонки из модели или таблицы.

    Args:
        model_class: SQLAlchemy модель или Table

    Returns:
        Множество имён числовых колонок
    """
    numeric_column_names = set()

    # Определяем числовые колонки из модели или таблицы
    if hasattr(model_class, "columns"):
        # Для SQLAlchemy Table или модели
        for col_name, col in model_class.columns.items():
            from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

            col_type = col.type
            # Проверяем по типу SQLAlchemy
            if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                numeric_column_names.add(col_name)
            # Проверяем по строковому представлению типа (для отражённых таблиц)
            elif hasattr(col_type, "__class__"):
                type_str = str(col_type).upper()
                if any(
                    t in type_str
                    for t in (
                        "NUMERIC",
                        "DECIMAL",
                        "DOUBLE PRECISION",
                        "REAL",
                        "FLOAT",
                        "INTEGER",
                        "BIGINT",
                        "SMALLINT",
                    )
                ):
                    numeric_column_names.add(col_name)
    elif hasattr(model_class, "__table__"):
        # Для ORM модели
        for col_name, col in model_class.__table__.columns.items():
            from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

            col_type = col.type
            if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                numeric_column_names.add(col_name)
            elif hasattr(col_type, "__class__"):
                type_str = str(col_type).upper()
                if any(
                    t in type_str
                    for t in (
                        "NUMERIC",
                        "DECIMAL",
                        "DOUBLE PRECISION",
                        "REAL",
                        "FLOAT",
                        "INTEGER",
                        "BIGINT",
                        "SMALLINT",
                    )
                ):
                    numeric_column_names.add(col_name)

    return numeric_column_names


def validate_numeric_types(
    records: list[dict[str, Any]],
    numeric_columns: set[str],
    row_offset: int = 0,
) -> None:
    """
    Валидация типов числовых колонок перед UPSERT.

    Проверяет, что все числовые значения имеют правильный тип (int, float, Decimal)
    и не содержат NaN/inf для float.

    Args:
        records: Список записей для валидации
        numeric_columns: Множество имён числовых колонок
        row_offset: Смещение для нумерации строк в ошибках

    Raises:
        TypeError: Если найдены строки в числовых колонках
        ValueError: Если найдены NaN/inf в числовых колонках
    """
    if not records:
        return

    errors: list[str] = []

    for row_idx, row in enumerate(records):
        actual_idx = row_offset + row_idx

        for col in numeric_columns:
            if col not in row:
                continue

            val = row[col]

            # None допустим - превратится в NULL
            if val is None:
                continue

            # Строки недопустимы в числовых колонках
            if isinstance(val, str):
                errors.append(
                    f"Row {actual_idx}: column '{col}' is str: {val!r} (type: {type(val).__name__})"
                )
                continue

            # Проверяем числовые типы
            if isinstance(val, int | float | Decimal | np.number):
                # Для float проверяем NaN/inf
                if isinstance(val, float | np.floating):
                    if not math.isfinite(val):
                        errors.append(
                            f"Row {actual_idx}: column '{col}' not finite: {val!r}"
                        )
                elif isinstance(val, np.integer):
                    # numpy integer типы допустимы
                    pass
                # int, Decimal допустимы
                continue

            # Неизвестный тип
            errors.append(
                f"Row {actual_idx}: column '{col}' has invalid type {type(val).__name__}: {val!r}"
            )

    if errors:
        error_msg = f"Type validation failed for {len(errors)} values:\n" + "\n".join(
            errors[:20]  # Показываем первые 20 ошибок
        )
        if len(errors) > 20:
            error_msg += f"\n... and {len(errors) - 20} more errors"
        logger.error(error_msg)
        raise TypeError(error_msg)


async def load_db_columns(session: AsyncSession, table_name: str) -> set[str]:
    """
    Загружает список колонок из схемы БД.

    Args:
        session: SQLAlchemy сессия
        table_name: Имя таблицы

    Returns:
        Множество имён колонок
    """
    query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name
        AND table_schema = 'public'
    """
    )

    result = await session.execute(query, {"table_name": table_name})
    columns = {
        row[0] for row in result.all()
    }  # FIXED: .all() instead of .fetchall() for async

    logger.info(f"Loaded {len(columns)} columns from {table_name}")
    return columns


def assert_required_fields(records: list[dict[str, Any]], required: set[str]) -> None:
    """
    Проверяет наличие обязательных полей в записях.

    Args:
        records: Список записей для проверки
        required: Множество обязательных полей

    Raises:
        ValueError: Если отсутствуют обязательные поля
    """
    if not records:
        raise ValueError("No records provided")

    first_record = records[0]
    missing_fields = required - set(first_record.keys())

    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    # Проверяем все записи
    for i, record in enumerate(records):
        missing_in_record = required - set(record.keys())
        if missing_in_record:
            raise ValueError(f"Record {i} missing required fields: {missing_in_record}")

    logger.info(f"All {len(records)} records have required fields: {required}")


def filter_problematic_fields(
    records: list[dict[str, Any]], problematic_fields: list[str] | None = None
) -> list[dict[str, Any]]:
    """
    Фильтрует проблемные поля из записей для избежания ошибок UPSERT.

    Args:
        records: Исходные записи
        problematic_fields: Список проблемных полей

    Returns:
        Отфильтрованные записи
    """
    if problematic_fields is None:
        problematic_fields = []  # Убрали все фильтры — колонки теперь в модели

    if not problematic_fields:
        # Нет проблемных полей — возвращаем как есть
        return records

    filtered_records = []
    for record in records:
        filtered_record = {
            k: v for k, v in record.items() if k not in problematic_fields
        }
        filtered_records.append(filtered_record)

    logger.info(
        f"Filtered out {len(problematic_fields)} problematic fields: {problematic_fields}"
    )
    return filtered_records


def sanitize_numeric_value(value: Any) -> float | None:
    """
    Очищает числовое значение от NaN/inf и приводит к float.

    Args:
        value: Значение для очистки

    Returns:
        Очищенное float значение или None если значение невалидно

    Raises:
        ValueError: Если значение не может быть очищено
    """
    if value is None:
        return None

    try:
        float_val = float(value)

        if np.isnan(float_val):
            return None
        if np.isinf(float_val):
            return None

        return float_val
    except (ValueError, TypeError, OverflowError) as e:
        logger.debug(f"Cannot convert {value} to float: {e}")
        return None


def sanitize_records(
    records: list[dict[str, Any]], db_cols: set[str]
) -> list[dict[str, Any]]:
    """
    Нормализует и фильтрует записи по схеме БД.

    Args:
        records: Исходные записи
        db_cols: Множество колонок БД

    Returns:
        Очищенные записи
    """
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

            # Обрабатываем None явно
            if value is None:
                sanitized_record[key] = None
            # Обрабатываем pandas Series/DataFrame — берём первое значение
            elif isinstance(value, pd.Series | pd.DataFrame):
                if len(value) > 0:
                    scalar_value = (
                        value.iloc[0]
                        if isinstance(value, pd.Series)
                        else value.iloc[0, 0]
                    )
                    # Рекурсивно обрабатываем scalar значение
                    if isinstance(scalar_value, int | float | np.number):
                        clean_value = sanitize_numeric_value(scalar_value)
                        sanitized_record[key] = clean_value
                    else:
                        sanitized_record[key] = (
                            None if pd.isna(scalar_value) else scalar_value
                        )
                else:
                    sanitized_record[key] = None
            # Обрабатываем числовые значения
            elif isinstance(value, int | float | np.number):
                clean_value = sanitize_numeric_value(value)
                # ВАЖНО: добавляем даже None, чтобы поле участвовало в UPSERT
                # Postgres заменит NULL при ON CONFLICT DO UPDATE
                sanitized_record[key] = clean_value
            # Обрабатываем строки и другие типы
            else:
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Пытаемся преобразовать строки в числа
                # для числовых колонок, чтобы избежать ошибок типов
                if isinstance(value, str):
                    # Пытаемся преобразовать строку в число
                    try:
                        # Пробуем float (включает int)
                        num_value = float(value)
                        sanitized_record[key] = num_value
                    except (ValueError, TypeError):
                        # Если не число, оставляем как строку
                        sanitized_record[key] = value
                else:
                    sanitized_record[key] = value

        sanitized.append(sanitized_record)

    if filtered_fields > 0:
        logger.info(
            f"Filtered out {filtered_fields} fields from {total_fields} total fields"
        )

    logger.info(f"Sanitized {len(sanitized)} records")
    return sanitized


def _clip_numeric_value(value: float, precision: int, scale: int) -> float:
    """
    Обрезает значение до допустимого диапазона для NUMERIC(precision, scale).

    Args:
        value: Числовое значение
        precision: Общая точность (количество цифр)
        scale: Количество цифр после запятой

    Returns:
        Обрезанное значение
    """
    # Максимальное значение для NUMERIC(precision, scale):
    # 10^(precision-scale) - 10^(-scale)
    # Например, для NUMERIC(10,4): 10^6 - 10^-4 = 999999.9999
    max_value = 10 ** (precision - scale) - 10 ** (-scale)
    min_value = -max_value

    if value > max_value:
        logger.warning(
            f"Value {value} exceeds NUMERIC({precision},{scale}) max ({max_value}), "
            f"clipping to {max_value}"
        )
        return max_value
    if value < min_value:
        logger.warning(
            f"Value {value} below NUMERIC({precision},{scale}) min ({min_value}), "
            f"clipping to {min_value}"
        )
        return min_value

    return value


def _normalize_value(value: Any, col_type: Any = None) -> Any:
    """
    Нормализует значение в базовый Python тип для SQLAlchemy.

    Args:
        value: Значение для нормализации
        col_type: Тип колонки SQLAlchemy (опционально, для проверки NUMERIC)

    Returns:
        Нормализованное значение (int, float, None, str, datetime и т.д.)
    """
    if value is None:
        return None

    # Проверяем pandas NaN
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    # Пытаемся преобразовать numpy/pandas типы в базовые Python типы
    try:
        # Проверяем numpy integer типы
        if isinstance(value, np.integer | np.int64 | np.int32 | np.int16 | np.int8):
            result = int(value)
            # Проверяем переполнение NUMERIC, если указан тип колонки
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

        # Проверяем numpy floating типы
        if isinstance(value, np.floating | np.float64 | np.float32 | np.float16):
            float_val = float(value)
            if np.isnan(float_val) or np.isinf(float_val):
                return None
            # Проверяем переполнение NUMERIC, если указан тип колонки
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

        # Проверяем pandas scalar типы (например, pd.Scalar)
        if hasattr(pd, "Scalar") and isinstance(value, pd.Scalar):
            try:
                scalar_val = value.item()
                return _normalize_value(scalar_val, col_type)  # Рекурсивно нормализуем
            except (AttributeError, ValueError):
                pass

        # Пытаемся преобразовать в float, если это число
        if isinstance(value, int | float):
            if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                return None
            result = value
            # Проверяем переполнение NUMERIC, если указан тип колонки
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

        # Пытаемся преобразовать другие числовые типы через item()
        if hasattr(value, "item"):
            try:
                item_val = value.item()
                return _normalize_value(item_val, col_type)  # Рекурсивно нормализуем
            except (AttributeError, ValueError):
                pass

        # Пытаемся преобразовать в float/int напрямую
        # Это обработает строки, которые содержат числа
        try:
            # Сначала пробуем float
            float_val = float(value)
            if np.isnan(float_val) or np.isinf(float_val):
                return None
            # Проверяем переполнение NUMERIC, если указан тип колонки
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
            # Если это целое число, возвращаем int
            if float_val.is_integer():
                return int(float_val)
            return float_val
        except (ValueError, TypeError, OverflowError):
            pass

        # Если это строка, которая не преобразовалась в число, оставляем как есть
        # (но для числовых колонок это будет обработано позже в build_upsert_statement)
        return value
    except Exception as e:
        logger.debug(f"Failed to normalize value {value} ({type(value)}): {e}")
        # В случае ошибки возвращаем None для безопасности
        return None


def build_upsert_statement(
    model_class,
    records: list[dict[str, Any]],
    pk: tuple[str, ...],
    db_cols: set[str] | None = None,
) -> Any:
    """
    Строит SQLAlchemy UPSERT statement.

    Args:
        model_class: SQLAlchemy модель или Table
        records: Записи для вставки
        pk: Первичные ключи
        db_cols: Колонки БД (если None, используется model_class.columns.keys())

    Returns:
        SQLAlchemy Insert statement с on_conflict_do_update
    """
    if not records:
        raise ValueError("No records provided for UPSERT")

    first_record = records[0]
    logger.info(f"Building UPSERT for {len(records)} records")
    logger.info(f"First record keys: {list(first_record.keys())}")
    logger.info(f"Sample values: {dict(list(first_record.items())[:5])}")

    # Получаем колонки из БД или модели для фильтрации
    if db_cols is not None:
        table_columns = db_cols
        logger.debug(f"Using DB columns: {len(table_columns)} total")
    else:
        table_columns = set(model_class.columns.keys())
        logger.debug(f"Using model columns: {len(table_columns)} total")

    # Фильтруем записи по колонкам таблицы
    filtered_records = []
    for record in records:
        filtered_record = {k: v for k, v in record.items() if k in table_columns}
        filtered_records.append(filtered_record)

    if filtered_records:
        removed_cols = set(first_record.keys()) - table_columns
        if removed_cols:
            logger.warning(
                f"Filtered out {len(removed_cols)} columns not in table: {sorted(removed_cols)[:10]}"
            )

    records = filtered_records
    if not records:
        raise ValueError("No valid records after filtering by table columns")

    first_record = records[0]

    # Финальная нормализация: преобразуем все значения в базовые Python типы
    # для избежания проблем с SQLAlchemy bound parameters
    normalized_records: list[dict[str, Any]] = []
    psar_types: set[str] = set()  # Для диагностики типов psar

    for record in records:
        normalized_record: dict[str, Any] = {}
        for key, value in record.items():
            # Диагностика для psar
            if key == "psar":
                psar_types.add(type(value).__name__)
                if len(psar_types) == 1 and len(normalized_records) == 0:
                    logger.debug(
                        f"First psar value type: {type(value)}, value: {value}"
                    )

            if value is None or pd.isna(value):
                normalized_record[key] = None
            elif isinstance(value, pd.Series | pd.DataFrame):
                # Обрабатываем pandas структуры
                if len(value) == 0:
                    normalized_record[key] = None
                else:
                    try:
                        scalar_value = (
                            value.iloc[0]
                            if isinstance(value, pd.Series)
                            else value.iloc[0, 0]
                        )
                        if pd.isna(scalar_value):
                            normalized_record[key] = None
                        else:
                            # Пытаемся преобразовать в базовый тип
                            normalized_record[key] = _normalize_value(scalar_value)
                    except Exception:
                        normalized_record[key] = None
            elif isinstance(value, np.ndarray):
                # Обрабатываем numpy массивы
                if value.size == 0:
                    normalized_record[key] = None
                else:
                    try:
                        scalar = value.flat[0]
                        normalized_record[key] = _normalize_value(scalar)
                    except Exception:
                        normalized_record[key] = None
            else:
                # Пытаемся нормализовать значение
                normalized_record[key] = _normalize_value(value)
        normalized_records.append(normalized_record)

    # Логируем типы psar для диагностики
    if psar_types:
        logger.debug(f"psar types found in batch: {psar_types}")
        # Проверяем, что все psar значения нормализованы
        psar_normalized_types = set()
        for record in normalized_records:
            if "psar" in record:
                psar_normalized_types.add(type(record["psar"]).__name__)
        logger.debug(f"psar normalized types: {psar_normalized_types}")

    # Убеждаемся, что все записи имеют одинаковый набор ключей
    # Это важно для SQLAlchemy, чтобы правильно обработать bound parameters
    if normalized_records:
        all_keys: set[str] = set()
        for record in normalized_records:
            all_keys.update(record.keys())

        # Добавляем отсутствующие ключи со значением None
        for record in normalized_records:
            for key in all_keys:
                if key not in record:
                    record[key] = None

    # Дополнительная нормализация: для числовых колонок преобразуем строки в числа
    # или None, чтобы избежать ошибок типа "column is of type double precision but expression is of type character varying"
    if normalized_records:
        numeric_column_names = set()

        # Определяем числовые колонки из модели или таблицы
        if hasattr(model_class, "columns"):
            # Для SQLAlchemy Table или модели
            for col_name, col in model_class.columns.items():
                from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

                col_type = col.type
                # Проверяем по типу SQLAlchemy
                if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                    numeric_column_names.add(col_name)
                # Проверяем по строковому представлению типа (для отражённых таблиц)
                elif hasattr(col_type, "__class__"):
                    type_str = str(col_type).upper()
                    if any(
                        t in type_str
                        for t in (
                            "NUMERIC",
                            "DECIMAL",
                            "DOUBLE PRECISION",
                            "REAL",
                            "FLOAT",
                            "INTEGER",
                            "BIGINT",
                            "SMALLINT",
                        )
                    ):
                        numeric_column_names.add(col_name)
        elif hasattr(model_class, "__table__"):
            # Для ORM модели
            for col_name, col in model_class.__table__.columns.items():
                from sqlalchemy.types import REAL, BigInteger, Float, Integer, Numeric

                col_type = col.type
                if isinstance(col_type, Numeric | Float | Integer | BigInteger | REAL):
                    numeric_column_names.add(col_name)
                elif hasattr(col_type, "__class__"):
                    type_str = str(col_type).upper()
                    if any(
                        t in type_str
                        for t in (
                            "NUMERIC",
                            "DECIMAL",
                            "DOUBLE PRECISION",
                            "REAL",
                            "FLOAT",
                            "INTEGER",
                            "BIGINT",
                            "SMALLINT",
                        )
                    ):
                        numeric_column_names.add(col_name)

        if numeric_column_names:
            logger.info(
                f"Normalizing {len(numeric_column_names)} numeric columns: {sorted(numeric_column_names)[:10]}..."
            )

            # Сохраняем типы колонок для правильной нормализации
            column_types: dict[str, Any] = {}
            if hasattr(model_class, "columns"):
                for col_name, col in model_class.columns.items():
                    if col_name in numeric_column_names:
                        column_types[col_name] = col.type
            elif hasattr(model_class, "__table__"):
                for col_name, col in model_class.__table__.columns.items():
                    if col_name in numeric_column_names:
                        column_types[col_name] = col.type

            # Диагностика: проверяем проблемные значения ДО нормализации
            problematic_values: dict[str, list[tuple[Any, type]]] = {}
            for record in normalized_records:
                for key in numeric_column_names:
                    if key in record:
                        value = record[key]
                        if value is not None and isinstance(value, str):
                            if key not in problematic_values:
                                problematic_values[key] = []
                            problematic_values[key].append((value, type(value)))

            if problematic_values:
                for key, samples in problematic_values.items():
                    logger.warning(
                        f"Found {len(samples)} string values in numeric column '{key}': {samples[:3]}"
                    )

            # Принудительная нормализация всех значений для числовых колонок
            for record in normalized_records:
                for key in numeric_column_names:
                    if key in record:
                        value = record[key]
                        if value is None:
                            continue
                        col_type = column_types.get(key)
                        if isinstance(value, str):
                            # Пытаемся преобразовать строку в число
                            # Проверяем, нужен ли int или float
                            try:
                                # Проверяем, является ли колонка integer по типу или строковому представлению
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

                                # Проверяем переполнение NUMERIC, если тип колонки известен
                                if (
                                    col_type
                                    and hasattr(col_type, "precision")
                                    and hasattr(col_type, "scale")
                                    and col_type.precision is not None
                                    and col_type.scale is not None
                                ):
                                    from sqlalchemy.types import Numeric

                                    if isinstance(col_type, Numeric):
                                        # Обрезаем значение перед преобразованием
                                        clipped = _clip_numeric_value(
                                            float(value),
                                            col_type.precision,
                                            col_type.scale,
                                        )
                                        if is_integer:
                                            normalized = int(clipped)
                                        else:
                                            normalized = clipped
                                    else:
                                        if is_integer:
                                            normalized = int(
                                                float(value)
                                            )  # Через float для "1.0" -> 1
                                        else:
                                            normalized = float(value)
                                else:
                                    if is_integer:
                                        normalized = int(
                                            float(value)
                                        )  # Через float для "1.0" -> 1
                                    else:
                                        normalized = float(value)
                                record[key] = normalized
                            except (ValueError, TypeError):
                                logger.warning(
                                    f"Failed to convert '{key}' value '{value}' to number, setting to None"
                                )
                                record[key] = None
                        elif value is not None and not isinstance(
                            value, int | float | np.number
                        ):
                            # Для других нечисловых типов пытаемся преобразовать
                            try:
                                normalized: float = float(value)
                                # Проверяем переполнение NUMERIC, если тип колонки известен
                                if (
                                    col_type
                                    and hasattr(col_type, "precision")
                                    and hasattr(col_type, "scale")
                                    and col_type.precision is not None
                                    and col_type.scale is not None
                                ):
                                    from sqlalchemy.types import Numeric

                                    if isinstance(col_type, Numeric):
                                        precision: int = col_type.precision
                                        scale: int = col_type.scale
                                        normalized = _clip_numeric_value(
                                            normalized, precision, scale
                                        )
                                record[key] = normalized
                            except (ValueError, TypeError):
                                logger.warning(
                                    f"Failed to convert '{key}' value '{value}' (type: {type(value)}) to float, setting to None"
                                )
                                record[key] = None
                        elif isinstance(value, np.number):
                            # Преобразуем numpy типы в Python типы
                            normalized: float | int = float(value)
                            # Проверяем переполнение NUMERIC, если тип колонки известен
                            if (
                                col_type
                                and hasattr(col_type, "precision")
                                and hasattr(col_type, "scale")
                                and col_type.precision is not None
                                and col_type.scale is not None
                            ):
                                from sqlalchemy.types import Numeric

                                if isinstance(col_type, Numeric):
                                    precision: int = col_type.precision
                                    scale: int = col_type.scale
                                    normalized = _clip_numeric_value(
                                        normalized, precision, scale
                                    )
                            record[key] = normalized

    # Создаём базовый INSERT statement
    stmt = pg_insert(model_class).values(normalized_records)
    logger.info("Base INSERT statement created")

    # Строим update_dict с правильным использованием excluded
    update_dict = {}
    non_pk_fields = [k for k in first_record if k not in pk]

    logger.info(f"Creating update_dict for {len(non_pk_fields)} non-PK fields")

    # Используем правильный способ формирования update_dict
    for field in non_pk_fields:
        try:
            # Получаем excluded значение для поля
            excluded_value = stmt.excluded[field]
            update_dict[field] = excluded_value
            logger.debug(f"Added field '{field}' to update_dict")
        except (KeyError, AttributeError) as e:
            logger.warning(f"Field '{field}' not available in stmt.excluded: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error with field '{field}': {e}")
            continue

    if not update_dict:
        raise ValueError("No fields available for UPSERT update")

    # Проверяем типы в update_dict
    logger.info(f"Update dict created with {len(update_dict)} fields")
    # NOTE: Avoided logging v.__name__ and v values directly as they may trigger sync operations on excluded objects

    # Добавляем on_conflict_do_update
    stmt = stmt.on_conflict_do_update(index_elements=list(pk), set_=update_dict)

    logger.info("UPSERT statement built successfully")
    return stmt


def validate_upsert_data(
    records: list[dict[str, Any]], db_cols: set[str], required_fields: set[str]
) -> None:
    """
    Выполняет полную валидацию данных перед UPSERT.

    Args:
        records: Записи для валидации
        db_cols: Колонки БД
        required_fields: Обязательные поля

    Raises:
        ValueError: При обнаружении проблем
    """
    # Проверяем обязательные поля
    assert_required_fields(records, required_fields)

    # Проверяем наличие критических полей
    critical_fields = ["ics_26", "rma_20", "t3_20"]
    missing_critical = []

    for field in critical_fields:
        if field in db_cols and not any(field in record for record in records):
            missing_critical.append(field)

    if missing_critical:
        logger.warning(f"Critical fields missing from all records: {missing_critical}")

    # Проверяем типы данных
    for i, record in enumerate(records):
        for key, value in record.items():
            if key in db_cols and isinstance(value, int | float | np.number):
                try:
                    sanitize_numeric_value(value)
                except ValueError as e:
                    logger.warning(f"Record {i}, field {key}: {e}")

    logger.info(f"Validation passed for {len(records)} records")


async def execute_upsert(
    session: AsyncSession, stmt: Any, records: list[dict[str, Any]]
) -> int:
    """
    Выполняет UPSERT с полной диагностикой.

    Args:
        session: SQLAlchemy сессия
        stmt: UPSERT statement
        records: Записи для вставки

    Returns:
        Количество вставленных записей
    """
    logger.info("Executing UPSERT statement...")
    logger.info(f"Statement type: {type(stmt)}")
    logger.info(f"UPSERT records count: {len(records)}")

    # Подсчитываем общее количество параметров
    if records:
        num_cols = len(records[0])
        total_params = len(records) * num_cols
        logger.info(
            f"UPSERT: {len(records)} rows × {num_cols} columns = {total_params} total parameters"
        )

        # Логируем первую запись для диагностики
        first_record = records[0]
        logger.debug(
            f"First record keys ({len(first_record)}): {list(first_record.keys())[:10]}..."
        )
        logger.debug(
            f"First record sample values: {dict(list(first_record.items())[:5])}"
        )

    try:
        # Пытаемся получить SQL строку для логирования (первые 500 символов)
        try:
            # Для async контекста compile может вызвать проблемы, но попробуем
            compiled = stmt.compile(compile_kwargs={"literal_binds": False})
            sql_str = str(compiled)
            sql_preview = sql_str[:500] if len(sql_str) > 500 else sql_str
            logger.info(f"UPSERT SQL preview (first 500 chars):\n{sql_preview}...")
        except Exception as compile_error:
            logger.debug(f"Could not compile SQL for logging: {compile_error}")

        result = await session.execute(stmt)

        # ДИАГНОСТИКА: Проверяем affected rows
        if hasattr(result, "rowcount"):
            logger.info(f"UPSERT affected rows: {result.rowcount}")
        else:
            logger.info("UPSERT result has no rowcount attribute")

        # NOTE: session.commit() is handled by the context manager (get_db_session)
        # Removed to avoid double commit which can cause greenlet_spawn errors

        logger.info(f"UPSERT: inserted {len(records)} records successfully")
        return len(records)

    except Exception as e:
        import traceback

        logger.error("=" * 80)
        logger.error("UPSERT EXECUTION FAILED")
        logger.error("=" * 80)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {e}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        logger.error(f"UPSERT records count: {len(records)}")

        if records:
            logger.error(f"First record keys: {list(records[0].keys())[:20]}...")
            logger.error(f"First record sample: {dict(list(records[0].items())[:10])}")

            # Пытаемся найти проблемные значения
            for i, record in enumerate(records[:5]):  # Проверяем первые 5 записей
                logger.error(f"Record {i} sample: {dict(list(record.items())[:5])}")

        logger.error("=" * 80)
        # NOTE: session.rollback() is handled by the context manager
        raise


async def build_and_execute_upsert(
    session: AsyncSession,
    model_class,
    records: list[dict[str, Any]],
    db_cols: set[str],
    pk: tuple[str, ...] = ("symbol", "timeframe", "timestamp"),
    required_fields: set[str] | None = None,
) -> int:
    """
    Полный цикл: валидация, очистка, построение и выполнение UPSERT.

    Args:
        session: SQLAlchemy сессия
        model_class: SQLAlchemy модель
        records: Записи для вставки
        db_cols: Колонки БД
        pk: Первичные ключи
        required_fields: Обязательные поля

    Returns:
        Количество вставленных записей
    """
    # 1. Валидация данных
    if required_fields is None:
        required_fields = {"symbol", "timeframe", "timestamp", "calculated_at"}
    validate_upsert_data(records, db_cols, required_fields)

    # 2. Очистка записей
    sanitized_records = sanitize_records(records, db_cols)

    logger.info(
        f"UPSERT: prepared {len(records)} records, sanitized {len(sanitized_records)} records"
    )

    if not sanitized_records:
        logger.warning("No valid records after sanitization")
        return 0

    # 2.5. Фильтруем проблемные поля ДО построения UPSERT statement
    filtered_records = filter_problematic_fields(sanitized_records)

    logger.info(
        f"UPSERT: after filtering problematic fields: {len(filtered_records)} records"
    )

    if not filtered_records:
        logger.warning("No valid records after filtering problematic fields")
        return 0

    # 2.7. Определяем числовые колонки для валидации
    numeric_columns = get_numeric_columns(model_class)
    logger.info(f"Found {len(numeric_columns)} numeric columns for validation")

    # 2.8. Валидация типов перед батчингом
    logger.info("Validating numeric types before batching...")
    try:
        validate_numeric_types(filtered_records, numeric_columns, row_offset=0)
        logger.info("✅ Type validation passed for all records")
    except (TypeError, ValueError) as validation_error:
        logger.error(f"Type validation failed: {validation_error}")
        raise

    # 2.9. Батчирование для избежания asyncpg лимита параметров (32767)
    # Примерная формула: num_params = batch_size * num_fields
    # PostgreSQL лимит: 32767 параметров
    # При ~147 полях: 147 × batch_size < 32767 → batch_size < 223
    # Используем константу BATCH_SIZE из модуля (50) или динамический расчёт
    if filtered_records:
        # Оцениваем количество полей по первой записи
        num_fields = len(filtered_records[0])
        # Безопасный размер батча: максимум 15000 параметров на батч
        calculated_batch_size = min(BATCH_SIZE, max(5, 15000 // num_fields))
        logger.info(
            f"Using batch size: {calculated_batch_size} (num_fields={num_fields}, max_params=15000, module BATCH_SIZE={BATCH_SIZE})"
        )
    else:
        calculated_batch_size = BATCH_SIZE
    total_saved = 0

    # РЕЖИМ ДИАГНОСТИКИ: одна строка - один запрос (пункт 6 плана)
    if DIAGNOSTIC_SINGLE_ROW:
        logger.warning("=" * 80)
        logger.warning("DIAGNOSTIC MODE: Processing records one by one")
        logger.warning("=" * 80)
        logger.warning(
            f"DIAGNOSTIC_SINGLE_ROW=1: Processing {len(filtered_records)} records individually"
        )

        for i, rec in enumerate(filtered_records):
            try:
                logger.info(f"Processing record {i+1}/{len(filtered_records)}...")
                # Валидация типов для одной записи
                validate_numeric_types([rec], numeric_columns, row_offset=i)

                stmt = build_upsert_statement(model_class, [rec], pk, db_cols)
                batch_saved = await execute_upsert(session, stmt, [rec])
                total_saved += batch_saved
                logger.info(f"✅ Record {i+1} saved successfully")
            except Exception:
                logger.error("=" * 80)
                logger.error(f"UPSERT FAILED on record {i+1}")
                logger.error("=" * 80)
                logger.error(f"Record sample: {dict(list(rec.items())[:10])}")
                logger.exception(f"Full error for record {i+1}:")
                raise

        logger.info(f"✅ Total saved in diagnostic mode: {total_saved}")
        return total_saved

    if len(filtered_records) > calculated_batch_size:
        logger.info(
            f"Splitting {len(filtered_records)} records into batches of {calculated_batch_size}"
        )
        num_batches = (len(filtered_records) - 1) // calculated_batch_size + 1

        for i in range(0, len(filtered_records), calculated_batch_size):
            batch = filtered_records[i : i + calculated_batch_size]
            batch_num = i // calculated_batch_size + 1
            logger.info(
                f"Processing batch {batch_num}/{num_batches} ({len(batch)} records, rows {i}-{i + len(batch) - 1})"
            )

            # Валидация типов для каждого батча
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
            except Exception as batch_error:
                logger.error(
                    f"UPSERT failed for batch {batch_num} (rows {i}-{i + len(batch) - 1}): {batch_error}"
                )
                raise

        logger.info(f"✅ Total saved across all batches: {total_saved}")
        return total_saved

    # Если записей немного, выполняем за один раз
    stmt = build_upsert_statement(model_class, filtered_records, pk, db_cols)
    return await execute_upsert(session, stmt, filtered_records)
