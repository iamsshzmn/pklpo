from __future__ import annotations

from src.db.migration_runner import _is_missing_migration_logs_error
from src.db.migrations.migrate_create_swap_ohlcv import CREATE_SWAP_OHLCV_TABLE_SQL
from src.db.migrations.migrate_recreate_swap_ohlcv_partitioned import (
    CREATE_PARTITIONED_SWAP_OHLCV_PARENT_SQL,
)
from src.db.migrations.migrate_swap_ohlcv_timestamps_timestamptz import (
    _build_alter_timestamp_type_sql,
    _build_set_default_now_sql,
)


def test_create_swap_ohlcv_migration_uses_timestamptz() -> None:
    assert "fetched_at TIMESTAMPTZ DEFAULT NOW()" in CREATE_SWAP_OHLCV_TABLE_SQL
    assert "created_at TIMESTAMPTZ DEFAULT NOW()" in CREATE_SWAP_OHLCV_TABLE_SQL


def test_recreate_swap_ohlcv_parent_uses_timestamptz() -> None:
    assert "fetched_at TIMESTAMPTZ DEFAULT NOW()" in CREATE_PARTITIONED_SWAP_OHLCV_PARENT_SQL
    assert "created_at TIMESTAMPTZ DEFAULT NOW()" in CREATE_PARTITIONED_SWAP_OHLCV_PARENT_SQL


def test_timestamptz_fix_migration_treats_existing_values_as_utc() -> None:
    sql = _build_alter_timestamp_type_sql("swap_ohlcv_p", "fetched_at")

    assert "TYPE TIMESTAMPTZ" in sql
    assert "USING fetched_at AT TIME ZONE 'UTC'" in sql


def test_timestamptz_fix_migration_sets_default_now_for_partitions() -> None:
    sql = _build_set_default_now_sql("public.swap_ohlcv_p_default", "created_at")

    assert "ALTER TABLE public.swap_ohlcv_p_default" in sql
    assert "ALTER COLUMN created_at" in sql
    assert "SET DEFAULT NOW()" in sql


def test_migration_runner_detects_broken_migration_logs_trigger() -> None:
    error = Exception('relation "migration_logs" does not exist')

    assert _is_missing_migration_logs_error(error) is True
