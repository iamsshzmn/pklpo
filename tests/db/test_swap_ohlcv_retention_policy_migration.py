from __future__ import annotations


def test_swap_ohlcv_retention_policy_documents_hot_only_1m_and_long_tf_sla() -> None:
    from src.db.migrations.migrate_swap_ohlcv_retention_policy import (
        RETENTION_POLICY,
    )

    assert RETENTION_POLICY == {
        "1m": 2,
        "5m": 7,
        "15m": 14,
        "30m": 30,
        "1H": 14,
        "4H": 60,
        "1D": 400,
        "1W": None,
        "1M": None,
    }


def test_swap_ohlcv_retention_migration_removes_insert_trigger_path() -> None:
    from src.db.migrations.migrate_swap_ohlcv_retention_policy import (
        SWAP_OHLCV_RETENTION_SQL,
    )

    sql = SWAP_OHLCV_RETENTION_SQL

    assert "CREATE TABLE IF NOT EXISTS swap_ohlcv_retention_policy" in sql
    assert "CREATE TABLE IF NOT EXISTS ops.swap_ohlcv_cleanup_audit" in sql
    assert "DROP TRIGGER IF EXISTS trigger_cleanup_swap_data" in sql
    assert "AFTER INSERT ON swap_ohlcv_p" not in sql
    assert "INTERVAL '2 days'" not in sql
    assert "retention_days IS NULL" in sql
    assert "DELETE FROM swap_ohlcv_p" in sql


def test_swap_ohlcv_retention_migration_is_registered() -> None:
    from src.db.migration_registry import get_migrations

    migrations = {migration.id: migration.name for migration in get_migrations()}

    assert migrations["340_swap_ohlcv_retention_policy"] == (
        "replace swap OHLCV insert-trigger cleanup with per-timeframe retention"
    )
