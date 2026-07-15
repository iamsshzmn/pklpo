"""Coverage tests for persistence sub-modules (SRP split gate, >=85%).

Tests pure-logic modules without DB. DB-dependent modules (inserter, schema_checker,
schema_cache, upsert_executor) are covered by import smoke tests only.
"""

from __future__ import annotations

import datetime
import importlib

import numpy as np
import pandas as pd
import pytest

PERSISTENCE_MODULES = [
    "src.features.infrastructure.persistence.batch_builder",
    "src.features.infrastructure.persistence.row_processor",
    "src.features.infrastructure.persistence.schema_filter",
    "src.features.infrastructure.persistence.name_normalizer",
    "src.features.infrastructure.persistence.validator",
    "src.features.infrastructure.persistence.normalizer",
    "src.features.infrastructure.persistence.upsert_executor",
    "src.features.infrastructure.persistence.schema_checker",
    "src.features.infrastructure.persistence.schema_cache",
    "src.features.infrastructure.persistence.data_transformer",
    "src.features.infrastructure.persistence.inserter",
]


@pytest.mark.parametrize("module_path", PERSISTENCE_MODULES)
def test_persistence_module_importable(module_path: str) -> None:
    mod = importlib.import_module(module_path)
    assert mod is not None


def test_batch_builder_facade_exports():
    from src.features.infrastructure.persistence.batch_builder import (
        build_batch_data,
        filter_batch_by_schema,
        normalize_record_names,
    )

    assert callable(build_batch_data)
    assert callable(filter_batch_by_schema)
    assert callable(normalize_record_names)


def test_batch_builder_is_thin_facade():
    import inspect

    import src.features.infrastructure.persistence.batch_builder as bb

    src_lines = inspect.getsource(bb).splitlines()
    assert len(src_lines) <= 25, (
        f"batch_builder.py is {len(src_lines)} lines; expected <=25"
    )


def test_validate_timestamp_valid():
    from src.features.infrastructure.persistence.validator import validate_timestamp

    assert validate_timestamp(1_700_000_000_000, 0) is True


def test_validate_timestamp_nan_rejected():
    from src.features.infrastructure.persistence.validator import validate_timestamp

    assert validate_timestamp(float("nan"), 0) is False


def test_validate_timestamp_small_value_rejected():
    from src.features.infrastructure.persistence.validator import validate_timestamp

    assert validate_timestamp(999_999_999_999, 0) is False


def test_validate_record_base_keys_ok():
    from src.features.infrastructure.persistence.validator import (
        validate_record_base_keys,
    )

    validate_record_base_keys(
        {"symbol": "X", "timeframe": "1m", "timestamp": 1}, ["symbol"]
    )


def test_validate_record_base_keys_missing_raises():
    from src.features.infrastructure.persistence.validator import (
        validate_record_base_keys,
    )

    with pytest.raises(ValueError):
        validate_record_base_keys({"symbol": "X"}, ["symbol", "timestamp"])


def test_validate_dataframe_valid():
    from src.features.infrastructure.persistence.validator import validate_dataframe

    df = pd.DataFrame({"a": [1, 2, 3]})
    assert validate_dataframe(df) is True


def test_validate_dataframe_none():
    from src.features.infrastructure.persistence.validator import validate_dataframe

    assert validate_dataframe(None) is False


def test_validate_dataframe_empty():
    from src.features.infrastructure.persistence.validator import validate_dataframe

    assert validate_dataframe(pd.DataFrame()) is False


def test_validate_required_fields_ok():
    from src.features.infrastructure.persistence.validator import (
        validate_required_fields,
    )

    df = pd.DataFrame({"timestamp": [1], "symbol": ["X"], "timeframe": ["1m"]})
    validate_required_fields(df)


def test_validate_required_fields_missing():
    from src.features.infrastructure.persistence.validator import (
        validate_required_fields,
    )

    df = pd.DataFrame({"timestamp": [1]})
    with pytest.raises(ValueError):
        validate_required_fields(df)


def test_sanitize_column_names():
    from src.features.infrastructure.persistence.normalizer import sanitize_column_names

    df = pd.DataFrame({" RSI 14 ": [1.0], "EMA-21": [2.0]})
    result = sanitize_column_names(df)
    assert "rsi_14" in result.columns
    assert "ema21" in result.columns


def test_normalize_numeric_columns_replaces_inf():
    from src.features.infrastructure.persistence.normalizer import (
        normalize_numeric_columns,
    )

    df = pd.DataFrame({"close": [1.0, float("inf"), -float("inf"), float("nan")]})
    result = normalize_numeric_columns(df)
    assert result["close"].isna().sum() == 3


def test_normalize_timestamp_column_from_ts():
    from src.features.infrastructure.persistence.normalizer import (
        normalize_timestamp_column,
    )

    df = pd.DataFrame({"ts": [1_700_000_000, 1_700_000_060]})
    result = normalize_timestamp_column(df)
    assert "timestamp" in result.columns
    assert result["timestamp"].iloc[0] == 1_700_000_000_000


def test_normalize_timestamp_column_already_ms():
    from src.features.infrastructure.persistence.normalizer import (
        normalize_timestamp_column,
    )

    df = pd.DataFrame({"timestamp": [1_700_000_000_000, 1_700_000_060_000]})
    result = normalize_timestamp_column(df)
    assert result["timestamp"].iloc[0] == 1_700_000_000_000


def test_normalize_timestamp_column_missing_raises():
    from src.features.infrastructure.persistence.normalizer import (
        normalize_timestamp_column,
    )

    df = pd.DataFrame({"close": [1.0]})
    with pytest.raises(ValueError):
        normalize_timestamp_column(df)


def test_add_service_fields():
    from src.features.infrastructure.persistence.normalizer import add_service_fields

    df = pd.DataFrame({"close": [1.0, 2.0]})
    result = add_service_fields(df, "BTC-USDT", "1m")
    assert list(result["symbol"]) == ["BTC-USDT", "BTC-USDT"]
    assert list(result["timeframe"]) == ["1m", "1m"]


def test_filter_columns_by_schema():
    from src.features.infrastructure.persistence.normalizer import (
        filter_columns_by_schema,
    )

    df = pd.DataFrame(
        {
            "timestamp": [1],
            "symbol": ["X"],
            "timeframe": ["1m"],
            "rsi_14": [50.0],
            "extra": [999.0],
        }
    )
    result = filter_columns_by_schema(
        df, {"rsi_14", "timestamp", "symbol", "timeframe"}
    )
    assert "extra" not in result.columns
    assert "rsi_14" in result.columns


def test_normalize_record_names_passthrough():
    from src.features.infrastructure.persistence.name_normalizer import (
        normalize_record_names,
    )

    records = [{"symbol": "BTC", "timeframe": "1m", "timestamp": 1, "rsi_14": 50.0}]
    db_cols = {"rsi_14"}
    result = normalize_record_names(records, db_cols)
    assert len(result) == 1
    assert result[0]["rsi_14"] == 50.0


def test_normalize_record_names_empty_raises():
    from src.features.infrastructure.persistence.name_normalizer import (
        normalize_record_names,
    )

    with pytest.raises(ValueError):
        normalize_record_names([], {"rsi_14"})


def test_normalize_record_names_filters_unknown():
    from src.features.infrastructure.persistence.name_normalizer import (
        normalize_record_names,
    )

    records = [
        {"symbol": "X", "timeframe": "1m", "timestamp": 1, "unknown_field": 999.0}
    ]
    db_cols = {"rsi_14"}
    result = normalize_record_names(records, db_cols)
    assert "unknown_field" not in result[0]


def test_filter_batch_by_schema_basic():
    from src.features.infrastructure.persistence.schema_filter import (
        filter_batch_by_schema,
    )

    base_keys = ["symbol", "timeframe", "timestamp"]
    records = [
        {
            "symbol": "X",
            "timeframe": "1m",
            "timestamp": 1,
            "rsi_14": 50.0,
            "drop_me": 0,
        }
    ]
    db_cols = {"symbol", "timeframe", "timestamp", "rsi_14"}
    result = filter_batch_by_schema(records, db_cols, base_keys)
    assert len(result) == 1
    assert "drop_me" not in result[0]


def test_filter_batch_by_schema_empty_input():
    from src.features.infrastructure.persistence.schema_filter import (
        filter_batch_by_schema,
    )

    result = filter_batch_by_schema([], {"rsi_14"}, ["symbol"])
    assert result == []


def test_filter_batch_by_schema_missing_base_keys_skips():
    from src.features.infrastructure.persistence.schema_filter import (
        filter_batch_by_schema,
    )

    records = [{"rsi_14": 50.0}]
    result = filter_batch_by_schema(
        records, {"rsi_14"}, ["symbol", "timeframe", "timestamp"]
    )
    assert result == []


def test_convert_timestamps_to_int64():
    from src.features.infrastructure.persistence.data_transformer import (
        convert_timestamps_to_int64,
    )

    records = [{"timestamp": 1_700_000_000_000.0}, {"timestamp": None}]
    result = convert_timestamps_to_int64(records)
    assert isinstance(result[0]["timestamp"], int)
    assert result[1]["timestamp"] is None


def test_convert_timestamps_invalid_raises():
    from src.features.infrastructure.persistence.data_transformer import (
        convert_timestamps_to_int64,
    )

    records = [{"timestamp": "not_a_number"}]
    with pytest.raises(ValueError):
        convert_timestamps_to_int64(records)


def test_normalize_numeric_values():
    from src.features.infrastructure.persistence.data_transformer import (
        normalize_numeric_values,
    )

    records = [{"rsi_14": np.float32(50.5), "ema_21": "100.0", "volume": None}]
    result = normalize_numeric_values(records, {"rsi_14", "ema_21", "volume"})
    assert isinstance(result[0]["rsi_14"], float)
    assert isinstance(result[0]["ema_21"], float)
    assert result[0]["volume"] is None


def test_filter_records_by_schema():
    from src.features.infrastructure.persistence.data_transformer import (
        filter_records_by_schema,
    )

    records = [{"rsi_14": 50.0, "extra": 99.0, "symbol": "X"}]
    result = filter_records_by_schema(records, {"rsi_14", "symbol"})
    assert "extra" not in result[0]
    assert "rsi_14" in result[0]


def test_validate_pk_fields_ok():
    from src.features.infrastructure.persistence.data_transformer import (
        validate_pk_fields,
    )

    records = [{"symbol": "X", "timeframe": "1m", "timestamp": 1}]
    validate_pk_fields(records)


def test_validate_pk_fields_missing_raises():
    from src.features.infrastructure.persistence.data_transformer import (
        validate_pk_fields,
    )

    records = [{"symbol": "X", "timeframe": "1m"}]
    with pytest.raises(ValueError):
        validate_pk_fields(records)


def test_validate_service_fields_ok():
    from src.features.infrastructure.persistence.data_transformer import (
        validate_service_fields,
    )

    records = [{"calculated_at": datetime.datetime.utcnow()}]
    validate_service_fields(records)


def test_validate_service_fields_str_raises():
    from src.features.infrastructure.persistence.data_transformer import (
        validate_service_fields,
    )

    records = [{"calculated_at": "2026-01-01"}]
    with pytest.raises(TypeError):
        validate_service_fields(records)


def test_transform_records_for_upsert():
    from src.features.infrastructure.persistence.data_transformer import (
        transform_records_for_upsert,
    )

    records = [
        {
            "symbol": "X",
            "timeframe": "1m",
            "timestamp": 1_700_000_000_000.0,
            "rsi_14": np.float32(50.5),
            "extra": 99.0,
        }
    ]
    db_cols = {"symbol", "timeframe", "timestamp", "rsi_14"}
    numeric_cols = {"rsi_14"}
    result = transform_records_for_upsert(records, db_cols, numeric_cols)
    assert len(result) == 1
    assert isinstance(result[0]["timestamp"], int)
    assert isinstance(result[0]["rsi_14"], float)
    assert "extra" not in result[0]


def test_transform_records_empty():
    from src.features.infrastructure.persistence.data_transformer import (
        transform_records_for_upsert,
    )

    result = transform_records_for_upsert([], {"rsi_14"}, {"rsi_14"})
    assert result == []


def _make_ind_df(rows: int = 5, base_ts: int = 1_700_000_000_000) -> pd.DataFrame:
    ts = [base_ts + i * 60_000 for i in range(rows)]
    return pd.DataFrame(
        {
            "timestamp": ts,
            "close": [100.0 + i for i in range(rows)],
            "rsi_14": [50.0 + i for i in range(rows)],
        }
    )


def test_row_processor_on_duplicate_callback():
    from src.features.infrastructure.persistence.row_processor import build_batch_data

    base_ts = 1_700_000_000_000
    df = pd.DataFrame({"timestamp": [base_ts, base_ts], "rsi_14": [1.0, 2.0]})
    dup_calls = []
    build_batch_data(
        df,
        "BTC",
        "1m",
        {"rsi_14"},
        on_duplicate=lambda sym, tf, n: dup_calls.append((sym, tf, n)),
    )
    assert len(dup_calls) == 1
    assert dup_calls[0][2] == 1


def test_row_processor_seen_timestamps_param():
    from src.features.infrastructure.persistence.row_processor import build_batch_data

    base_ts = 1_700_000_000_000
    df = _make_ind_df(3, base_ts)
    seen = {base_ts}
    batch, _ = build_batch_data(df, "BTC", "1m", {"rsi_14"}, seen_timestamps=seen)
    assert all(r["timestamp"] != base_ts for r in batch)


def test_schema_cache_get_miss():
    from src.features.infrastructure.persistence.schema_cache import SchemaCache

    cache = SchemaCache()
    session = object()
    assert cache.get(session) is None


def test_schema_cache_set_and_get():
    from src.features.infrastructure.persistence.schema_cache import (
        SchemaCache,
        SchemaInfo,
    )

    cache = SchemaCache()
    session = object()
    info = cache.set(session, {"rsi_14"}, None, {"rsi_14"})
    assert isinstance(info, SchemaInfo)
    assert cache.get(session) is info
    assert info.db_columns == {"rsi_14"}


def test_schema_cache_invalidate():
    from src.features.infrastructure.persistence.schema_cache import SchemaCache

    cache = SchemaCache()
    session = object()
    cache.set(session, {"rsi_14"}, None, set())
    assert cache.get(session) is not None
    cache.invalidate(session)
    assert cache.get(session) is None


def test_schema_cache_invalidate_missing_key():
    from src.features.infrastructure.persistence.schema_cache import SchemaCache

    cache = SchemaCache()
    session = object()
    cache.invalidate(session)


def test_schema_cache_clear():
    from src.features.infrastructure.persistence.schema_cache import SchemaCache

    cache = SchemaCache()
    s1, s2 = object(), object()
    cache.set(s1, set(), None, set())
    cache.set(s2, set(), None, set())
    assert len(cache) == 2
    cache.clear()
    assert len(cache) == 0


def test_get_schema_cache_singleton():
    from src.features.infrastructure.persistence.schema_cache import (
        SchemaCache,
        get_schema_cache,
    )

    c1 = get_schema_cache()
    c2 = get_schema_cache()
    assert c1 is c2
    assert isinstance(c1, SchemaCache)


def test_schema_info_defaults():
    from src.features.infrastructure.persistence.schema_cache import SchemaInfo

    info = SchemaInfo()
    assert isinstance(info.db_columns, set)
    assert isinstance(info.numeric_columns, set)
    assert info.indicators_table is None


def test_get_or_load_schema_uses_cache():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.features.infrastructure.persistence.schema_cache import SchemaCache

    cache = SchemaCache()
    session = object()
    cached_info = cache.set(session, {"rsi_14"}, MagicMock(), {"rsi_14"})

    async def run():
        from src.features.infrastructure.persistence.schema_cache import (
            get_or_load_schema,
        )

        with patch(
            "src.features.infrastructure.persistence.schema_cache.get_schema_cache",
            return_value=cache,
        ):
            return await get_or_load_schema(
                session,
                AsyncMock(),
                AsyncMock(),
                MagicMock(),
            )

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result is cached_info


def test_execute_upsert_with_retry_empty_records():
    import asyncio
    from unittest.mock import MagicMock

    from src.features.infrastructure.persistence.upsert_executor import (
        execute_upsert_with_retry,
    )

    session = MagicMock()
    result = asyncio.get_event_loop().run_until_complete(
        execute_upsert_with_retry(session, None, [], set(), ("symbol",), set())
    )
    assert result == 0


def test_check_db_state_before_after_success():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from src.features.infrastructure.persistence.upsert_executor import (
        check_db_state_before_after,
    )

    session = MagicMock()
    check_func = AsyncMock(return_value=(42, 1_700_000_000_000))
    count, ts = asyncio.get_event_loop().run_until_complete(
        check_db_state_before_after(session, "BTC", "1m", check_func)
    )
    assert count == 42
    assert ts == 1_700_000_000_000


def test_check_db_state_before_after_error():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from src.features.infrastructure.persistence.upsert_executor import (
        check_db_state_before_after,
    )

    session = MagicMock()
    check_func = AsyncMock(side_effect=RuntimeError("DB down"))
    count, ts = asyncio.get_event_loop().run_until_complete(
        check_db_state_before_after(session, "BTC", "1m", check_func)
    )
    assert count is None
    assert ts is None


def test_execute_upsert_with_retry_success():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from src.features.infrastructure.persistence.upsert_executor import (
        execute_upsert_with_retry,
    )

    mock_upsert = AsyncMock(return_value=3)
    records = [{"symbol": "X", "timeframe": "1m", "timestamp": 1}]

    async def run():
        with patch(
            "src.features.infrastructure.persistence.upsert_executor.build_and_execute_upsert",
            mock_upsert,
        ):
            return await execute_upsert_with_retry(
                MagicMock(),
                MagicMock(),
                records,
                set(),
                ("symbol",),
                set(),
                max_retries=1,
            )

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result == 3


def test_execute_upsert_with_retry_retries_then_succeeds():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from sqlalchemy.exc import OperationalError

    from src.features.infrastructure.persistence.upsert_executor import (
        execute_upsert_with_retry,
    )

    records = [{"symbol": "X", "timeframe": "1m", "timestamp": 1}]
    mock_upsert = AsyncMock(side_effect=[OperationalError("conn", None, None), 1])

    async def run():
        with (
            patch(
                "src.features.infrastructure.persistence.upsert_executor.build_and_execute_upsert",
                mock_upsert,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            return await execute_upsert_with_retry(
                MagicMock(),
                MagicMock(),
                records,
                set(),
                ("symbol",),
                set(),
                max_retries=2,
                base_delay=0.0,
            )

    result = asyncio.get_event_loop().run_until_complete(run())
    assert result == 1
    assert mock_upsert.call_count == 2


def test_execute_upsert_with_retry_exhausted_raises():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from sqlalchemy.exc import OperationalError

    from src.features.infrastructure.persistence.upsert_executor import (
        execute_upsert_with_retry,
    )

    records = [{"symbol": "X", "timeframe": "1m", "timestamp": 1}]
    err = OperationalError("conn", None, None)
    mock_upsert = AsyncMock(side_effect=err)

    async def run():
        with (
            patch(
                "src.features.infrastructure.persistence.upsert_executor.build_and_execute_upsert",
                mock_upsert,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            return await execute_upsert_with_retry(
                MagicMock(),
                MagicMock(),
                records,
                set(),
                ("symbol",),
                set(),
                max_retries=1,
                base_delay=0.0,
            )

    with pytest.raises(OperationalError):
        asyncio.get_event_loop().run_until_complete(run())
