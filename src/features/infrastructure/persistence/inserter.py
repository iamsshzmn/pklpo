"""
Main inserter function for indicators.
"""

import logging

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from ...schema.schema_manager import SchemaManager
from ..diagnostics import check_df_schema, diagnose_dataframe_issues, diagnose_df
from ..upsert_builder import build_and_execute_upsert
from .batch_builder import (
    build_batch_data,
    filter_batch_by_schema,
    normalize_record_names,
)
from .normalizer import (
    add_service_fields,
    filter_columns_by_schema,
    normalize_numeric_columns,
    normalize_timestamp_column,
    sanitize_column_names,
)
from .schema_checker import (
    check_schema_and_search_path,
    check_unique_index,
    load_db_columns,
    reflect_indicators_table,
)
from .validator import validate_dataframe, validate_required_fields

logger = logging.getLogger(__name__)

# Константы
REQUIRED_FIELDS = {"timestamp", "symbol", "timeframe"}


async def insert_indicators(
    session: AsyncSession,
    ind_df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> int:
    """
    Batch UPSERT индикаторов в базу данных с единым реестром колонок.

    Выполняет массовую вставку/обновление индикаторов в таблицу `indicators`.
    Использует схема-менеджер для валидации данных и отражение схемы БД
    для совместимости. Критические поля сохраняются даже с NaN значениями.

    Args:
        session: Асинхронная SQLAlchemy сессия
        ind_df: DataFrame с рассчитанными индикаторами (должен содержать
                колонки timestamp, symbol, timeframe)
        symbol: Символ инструмента (например, 'BTC-USDT-SWAP')
        timeframe: Таймфрейм (например, '1m', '5m', '1h')

    Returns:
        Количество успешно сохранённых записей

    Raises:
        ValueError: Если отсутствуют обязательные поля или данные невалидны

    Example:
        >>> from sqlalchemy.ext.asyncio import AsyncSession
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'timestamp': [1609459200000, 1609459260000],
        ...     'rsi_14': [50.5, 51.2],
        ...     'sma_20': [100.0, 101.0]
        ... })
        >>> # async with get_db_session() as session:
        >>> #     count = await insert_indicators(session, df, 'BTC-USDT', '1m')
        >>> #     print(f"Saved {count} records")
    """
    # Логирование вызова функции
    logger.info(
        f"INSERT_INDICATORS: symbol={symbol}, timeframe={timeframe}, df_shape={ind_df.shape if ind_df is not None else 'None'}"
    )
    logger.debug(
        f"DataFrame columns: {list(ind_df.columns) if ind_df is not None else 'None'}"
    )

    # Валидация входных данных
    if not validate_dataframe(ind_df):
        return 0

    # Инициализируем схема-менеджер
    schema_manager = SchemaManager()
    logger.info(f"Schema info: {schema_manager.get_schema_info()}")

    # ✅ Schema is managed ONLY through Alembic migrations
    logger.info(
        "Schema is managed through Alembic migrations only (no runtime changes)"
    )

    # ДИАГНОСТИКА 1: Проверка уникального индекса
    await check_unique_index(session)

    # ДИАГНОСТИКА 2: Проверка схемы и search_path
    await check_schema_and_search_path(session)

    # Sanitize column names
    ind_df = sanitize_column_names(ind_df)

    # Нормализация числовых колонок
    ind_df = normalize_numeric_columns(ind_df)

    logger.info(f"Inserting indicators: DataFrame shape: {ind_df.shape}")
    logger.info(f"DataFrame columns: {list(ind_df.columns)}")

    # Диагностика DataFrame перед обработкой
    diagnosis = diagnose_dataframe_issues(ind_df)
    if diagnosis["issues"]:
        logger.warning(f"DataFrame issues detected: {diagnosis['issues']}")

    # Быстрая диагностика на лету
    quick_diag = diagnose_df(ind_df)
    logger.info(f"QUICK DIAGNOSTICS: {quick_diag}")

    # Единый источник схемы (для диагностики)
    table_cols = {
        "symbol",
        "timeframe",
        "timestamp",
        "calculated_at",
        "ema_12",
        "ema_21",
        "ema_26",
        "ema_50",
        "ema_200",
        "sma_20",
        "sma_34",
        "sma_50",
        "sma_200",
        "rsi_14",
        "atr_14",
        "adx_14",
        "adx_pos_di",
        "adx_neg_di",
        "macd",
        "macd_signal",
        "macd_histogram",
        "obv",
        "vwap",
    }
    actual = set(ind_df.columns)
    extra_in_df = sorted(actual - table_cols)
    missing_in_df = sorted(table_cols - actual)

    # Диагностика значений
    num_cols = ind_df.select_dtypes(include=["number"]).columns
    obj_cols = ind_df.select_dtypes(include=["object"]).columns
    inf_total = (
        int(np.isinf(ind_df[num_cols]).to_numpy().sum()) if len(num_cols) > 0 else 0
    )
    nan_total = int(ind_df.isna().to_numpy().sum())

    # Единый блок диагностики
    logger.info("SCHEMA DIAGNOSTICS:")
    logger.info(f"  shape: {ind_df.shape}")
    logger.info(f"  columns: {sorted(ind_df.columns)}")
    logger.info(f"  extra_in_df: {extra_in_df}")
    logger.info(f"  missing_in_df: {missing_in_df}")
    logger.info(f"  object_cols: {list(obj_cols)}")
    logger.info(f"  inf_total: {inf_total}")
    logger.info(f"  nan_total: {nan_total}")

    # Добавляем служебные поля
    ind_df = add_service_fields(ind_df, symbol, timeframe)

    # Нормализуем timestamp
    ind_df = normalize_timestamp_column(ind_df)

    # Загружаем схему БД
    db_cols = await load_db_columns(session)

    # Проверяем отсутствующие колонки
    calc_cols = set(ind_df.columns) - {"ts", "open", "high", "low", "close", "volume"}
    missing = sorted(calc_cols - db_cols)
    if missing:
        logger.warning(
            f"Columns in DataFrame but not in DB schema: {missing[:10]}{'...' if len(missing) > 10 else ''}"
        )
        logger.warning(
            "These columns will be filtered out. Use Alembic migrations to add new columns."
        )
        logger.info(
            "To add these columns, create an Alembic migration: alembic revision -m 'Add missing indicators'"
        )

    # Диагностика overlap индикаторов перед фильтрацией
    overlap_indicators = ["hlc3", "hl2", "ohlc4", "wcp"]
    overlap_in_df = [c for c in overlap_indicators if c in ind_df.columns]
    overlap_in_db = [c for c in overlap_indicators if c in db_cols]
    logger.info(
        f"DIAGNOSTIC: Overlap indicators - in DataFrame: {overlap_in_df}, in DB: {overlap_in_db}"
    )
    if overlap_in_df:
        for col in overlap_in_df:
            non_null = ind_df[col].notna().sum()
            logger.info(f"  {col}: {non_null}/{len(ind_df)} non-null in DataFrame")

    # Фильтруем колонки по схеме БД
    ind_df = filter_columns_by_schema(ind_df, db_cols)

    # Проверяем overlap индикаторы после фильтрации
    overlap_after_filter = [c for c in overlap_indicators if c in ind_df.columns]
    logger.info(f"DIAGNOSTIC: Overlap indicators after filter: {overlap_after_filter}")
    if overlap_after_filter:
        for col in overlap_after_filter:
            non_null = ind_df[col].notna().sum()
            logger.info(f"  {col}: {non_null}/{len(ind_df)} non-null after filter")

    # Проверяем наличие обязательных полей после фильтрации
    validate_required_fields(ind_df)

    # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: DF перед build_batch_data (пункт 2 плана)
    logger.info("=" * 80)
    logger.info("DETAILED LOGGING: DataFrame before build_batch_data")
    logger.info("=" * 80)
    logger.info(f"DF shape: {ind_df.shape}")
    logger.info(f"DF columns ({len(ind_df.columns)}): {list(ind_df.columns)[:20]}...")
    logger.info(f"DF dtypes:\n{ind_df.dtypes.head(30)}")
    logger.info(
        f"DF first row sample:\n{ind_df.head(1).to_dict('records')[0] if not ind_df.empty else 'empty'}"
    )

    # Собираем batch data
    batch_data, skipped_rows = build_batch_data(ind_df, symbol, timeframe, db_cols)

    if not batch_data:
        logger.warning("No valid data to insert")
        return 0

    # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: Первая запись после build_batch_data
    logger.info("=" * 80)
    logger.info("DETAILED LOGGING: First record after build_batch_data")
    logger.info("=" * 80)
    logger.info(f"First record sample: {batch_data[0]}")
    logger.info(
        f"First record keys ({len(batch_data[0])}): {list(batch_data[0].keys())[:20]}..."
    )

    # Базовые ключи, которые должны быть сохранены
    base_keys = ["symbol", "timeframe", "timestamp", "calculated_at"]

    # Фильтруем batch по схеме
    batch_data = filter_batch_by_schema(batch_data, db_cols, base_keys)

    # Нормализуем имена полей
    batch_data = normalize_record_names(batch_data, db_cols)

    # Валидация схемы перед UPSERT
    schema_check = check_df_schema(pd.DataFrame(batch_data), table_cols)
    if not schema_check["schema_match"]:
        logger.warning(
            f"Schema mismatch: extra={schema_check['extra_cols']}, missing={schema_check['missing_cols']}"
        )

    # Инициализируем stmt для безопасности
    try:
        # Логируем детали первой записи для отладки
        if batch_data:
            first_record = batch_data[0]
            logger.info(f"First record keys: {list(first_record.keys())}")
            if "ema_200" in first_record:
                logger.info(
                    f"ema_200 value: {first_record['ema_200']} (type: {type(first_record['ema_200'])})"
                )

        # Валидация данных через схема-менеджер
        logger.info(f"Validating {len(batch_data)} records with schema manager...")
        validation_result = schema_manager.validate_data(batch_data)

        if not validation_result["valid"]:
            logger.error(f"Data validation failed: {validation_result['errors']}")
            raise ValueError(f"Data validation failed: {validation_result['errors']}")

        if validation_result["warnings"]:
            logger.warning(
                f"Data validation warnings: {validation_result['warnings'][:10]}"
            )  # Первые 10

        # Используем валидированные и маппированные записи
        validated_records = validation_result["mapped_records"]
        logger.info(f"Using {len(validated_records)} validated records")

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Фильтруем по db_cols ПОСЛЕ валидации схемы
        # Схема-менеджер может вернуть поля, которых ещё нет в БД
        final_filtered_records = []
        for record in validated_records:
            final_record = {k: v for k, v in record.items() if k in db_cols}
            final_filtered_records.append(final_record)

        if final_filtered_records:
            missing_cols = set(validated_records[0].keys()) - db_cols
            if missing_cols:
                logger.warning(
                    f"Filtered out {len(missing_cols)} columns not in DB: {sorted(missing_cols)[:10]}"
                )

        validated_records = final_filtered_records
        logger.info(f"Final filtered records: {len(validated_records)}")

        # ДИАГНОСТИКА 3: Проверка payload после фильтрации
        logger.info("🔍 DIAGNOSTIC 3: Checking payload after filtering...")
        if validated_records:
            first_record = validated_records[0]
            pk_fields = {"symbol", "timeframe", "timestamp"}
            non_pk_fields = [k for k in first_record if k not in pk_fields]

            logger.info(
                f"First record keys after sanitize: {list(first_record.keys())}"
            )
            logger.info(f"Non-PK fields count: {len(non_pk_fields)}")
            logger.info(f"Non-PK fields: {non_pk_fields[:10]}...")  # Первые 10

            # Проверяем типы критических полей
            logger.info(
                f"Timestamp type: {type(first_record.get('timestamp'))}, value: {first_record.get('timestamp')}"
            )
            logger.info(
                f"Calculated_at type: {type(first_record.get('calculated_at'))}, value: {first_record.get('calculated_at')}"
            )

            # Проверяем числовые поля
            numeric_fields = [
                k
                for k, v in first_record.items()
                if isinstance(v, int | float) and k not in pk_fields
            ]
            logger.info(f"Numeric fields count: {len(numeric_fields)}")
            logger.info(
                f"Sample numeric values: {[(k, v, type(v)) for k, v in list(first_record.items())[:5] if isinstance(v, int | float)]}"
            )

        # Отражение таблицы из БД
        indicators_table = await reflect_indicators_table(session)

        # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: Схема таблицы (пункт 3 плана)
        logger.info("=" * 80)
        logger.info("DETAILED LOGGING: Indicators table schema")
        logger.info("=" * 80)
        logger.info(f"Table name: {indicators_table.name}")
        logger.info(f"Total columns: {len(indicators_table.columns)}")

        # Логируем типы колонок
        schema_info: dict[str, str] = {}
        for col in indicators_table.columns.values():
            col_name = col.name
            col_type_str = str(col.type).upper()
            schema_info[col_name] = col_type_str
            if col_name in [
                "symbol",
                "timeframe",
                "timestamp",
                "calculated_at",
                "ultosc",
                "stochrsi_k",
                "cdl_doji",
            ]:
                python_type = getattr(col.type, "python_type", type(None))
                logger.info(
                    f"  {col_name}: {col_type_str} (Python type: {python_type})"
                )

        logger.info(f"Schema info summary: {len(schema_info)} columns")
        logger.info(f"Sample schema types: {dict(list(schema_info.items())[:10])}")

        # Проверяем наличие критических колонок в отражённой таблице
        critical_cols = {
            "hl2",
            "hlc3",
            "ohlc4",
            "bb_upper",
            "bb_middle",
            "bb_lower",
        }
        table_cols_set = set(indicators_table.columns.keys())
        missing_critical = critical_cols - table_cols_set
        if missing_critical:
            logger.warning(
                f"Critical columns missing in reflected table: {missing_critical}"
            )
        else:
            logger.info(
                f"✅ All critical columns present in reflected table: {critical_cols}"
            )

        logger.info(f"DB columns: {len(db_cols)} total")
        logger.info(
            f"Schema registry columns: {len(schema_manager.get_all_columns())} total"
        )

        # Проверяем соответствие схемы
        missing_in_db = schema_manager.get_all_columns() - db_cols
        if missing_in_db:
            logger.warning(f"Schema columns not in DB: {missing_in_db}")
            # Не выбрасываем ошибку - колонки могут быть добавлены через миграции

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Приводим timestamp к int64 перед UPSERT
        logger.info("Converting timestamp to int64 for all records...")
        for record in validated_records:
            if "timestamp" in record and record["timestamp"] is not None:
                try:
                    # Приводим к int64
                    if isinstance(record["timestamp"], float) or isinstance(
                        record["timestamp"], int | np.integer
                    ):
                        record["timestamp"] = int(record["timestamp"])
                    else:
                        # Пытаемся преобразовать
                        record["timestamp"] = int(float(record["timestamp"]))
                except (ValueError, TypeError, OverflowError) as e:
                    logger.error(
                        f"Failed to convert timestamp to int64: {record.get('timestamp')}, error: {e}"
                    )
                    raise ValueError(
                        f"Invalid timestamp value: {record.get('timestamp')}"
                    ) from e

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Нормализуем числовые значения для всех числовых колонок БД
        # Преобразуем строки в числа, чтобы избежать ошибок типа "column is of type double precision but expression is of type character varying"
        logger.info("Normalizing numeric values for all records...")
        numeric_cols = {
            col.name
            for col in indicators_table.columns
            if col.type.python_type in (int, float)
            or str(col.type).upper()
            in ("NUMERIC", "DOUBLE PRECISION", "REAL", "FLOAT", "INTEGER", "BIGINT")
        }
        logger.info(f"Found {len(numeric_cols)} numeric columns to normalize")

        for record in validated_records:
            for key in numeric_cols:
                if key in record:
                    value = record[key]
                    if value is None:
                        continue
                    if isinstance(value, str):
                        # Пытаемся преобразовать строку в число
                        try:
                            record[key] = float(value)
                        except (ValueError, TypeError):
                            record[key] = None
                    elif not isinstance(value, int | float | np.number):
                        # Для других нечисловых типов пытаемся преобразовать
                        try:
                            record[key] = float(value)
                        except (ValueError, TypeError):
                            record[key] = None
                    elif isinstance(value, np.number):
                        # Преобразуем numpy типы в Python типы
                        record[key] = float(value)

        # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ: После normalize_numeric_columns (пункт 2 плана)
        logger.info("=" * 80)
        logger.info("DETAILED LOGGING: First record after normalize_numeric_columns")
        logger.info("=" * 80)
        if validated_records:
            first_record = validated_records[0]
            logger.info(f"First record sample: {dict(list(first_record.items())[:10])}")
            # Проверяем типы критических числовых полей
            critical_numeric = ["ultosc", "stochrsi_k", "cdl_doji", "willr", "rsi_14"]
            for col in critical_numeric:
                if col in first_record:
                    val = first_record[col]
                    logger.info(f"  {col}: {val!r} (type: {type(val).__name__})")

        # ПРОВЕРКА КОНТРАКТА UPSERT (пункт 5 плана)
        logger.info("=" * 80)
        logger.info("UPSERT CONTRACT VALIDATION")
        logger.info("=" * 80)

        pk_fields = {"symbol", "timeframe", "timestamp"}
        service_fields = {"calculated_at", "created_at", "updated_at"}

        for i, record in enumerate(validated_records):
            # Проверка PK полей
            for pk_field in pk_fields:
                if pk_field not in record or record[pk_field] is None:
                    raise ValueError(
                        f"Row {i}: PK field '{pk_field}' is missing or NULL"
                    )
                # Проверка типа timestamp
                if pk_field == "timestamp":
                    if not isinstance(record[pk_field], int | np.integer):
                        logger.warning(
                            f"Row {i}: timestamp type is {type(record[pk_field])}, expected int"
                        )

            # Проверка служебных полей
            for service_field in service_fields:
                if service_field in record and record[service_field] is not None:
                    if isinstance(record[service_field], str):
                        raise TypeError(
                            f"Row {i}: service field '{service_field}' is str, expected datetime or None"
                        )

        logger.info(
            f"✅ UPSERT contract validation passed for {len(validated_records)} records"
        )

        # ДИАГНОСТИКА 4: Проверка состояния БД до UPSERT
        from .schema_checker import check_db_state

        logger.info("🔍 DIAGNOSTIC 4: Checking database state before UPSERT...")
        count_before, max_timestamp_before = await check_db_state(
            session, symbol, timeframe
        )
        if count_before is not None:
            logger.info(
                f"DB state before UPSERT: {count_before} rows, max_timestamp: {max_timestamp_before}"
            )

        # PRE-UPSERT LOGGING: Log details about what we're about to insert
        logger.info(
            f"🔧 PRE-UPSERT: Preparing to insert {len(validated_records)} records"
        )
        if validated_records:
            first_rec = validated_records[0]
            logger.debug(f"🔧 PRE-UPSERT: First record keys: {list(first_rec.keys())}")
            logger.debug(
                f"🔧 PRE-UPSERT: First record sample values: {dict(list(first_rec.items())[:5])}"
            )
            logger.debug(
                f"🔧 PRE-UPSERT: PK values - symbol={first_rec.get('symbol')}, timeframe={first_rec.get('timeframe')}, timestamp={first_rec.get('timestamp')} (type: {type(first_rec.get('timestamp'))})"
            )

            # Count non-null feature values
            non_null_features = sum(
                1
                for k, v in first_rec.items()
                if k not in {"symbol", "timeframe", "timestamp", "calculated_at"}
                and v is not None
                and not (isinstance(v, float) and pd.isna(v))
            )
            logger.info(
                f"🔧 PRE-UPSERT: First record has {non_null_features} non-null feature values"
            )

        saved_count = await build_and_execute_upsert(
            session=session,
            model_class=indicators_table,  # Используем отражённую таблицу вместо модели
            records=validated_records,
            db_cols=db_cols,
            pk=("symbol", "timeframe", "timestamp"),
            required_fields=schema_manager.get_required_fields(),
        )

        # ДИАГНОСТИКА 5: Проверка состояния БД после UPSERT
        logger.info("🔍 DIAGNOSTIC 5: Checking database state after UPSERT...")
        count_after, max_timestamp_after = await check_db_state(
            session, symbol, timeframe
        )
        if count_after is not None:
            logger.info(
                f"DB state after UPSERT: {count_after} rows, max_timestamp: {max_timestamp_after}"
            )

            # Проверяем, что данные действительно добавились
            rows_added = count_after - (count_before or 0)
            logger.info(f"Rows added: {rows_added}")

            if rows_added == 0 and saved_count > 0:
                logger.warning(
                    "UPSERT attempted %s records but inserted 0 new rows (likely duplicates by PK)",
                    saved_count,
                )
            elif rows_added > 0:
                logger.info(f"UPSERT successful: {rows_added} rows added")

        logger.info(
            f"Successfully saved {saved_count} records using schema-managed approach"
        )
        return saved_count

    except Exception as e:
        import traceback

        logger.error(f"Database insertion failed: {e}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        logger.error(f"Batch data sample: {batch_data[0] if batch_data else 'empty'}")
        await session.rollback()
        raise
