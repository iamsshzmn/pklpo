from __future__ import annotations


def test_continuous_build_audit_migration_contract() -> None:
    from src.db.migrations.migrate_create_continuous_ohlcv_build_audit import (
        CONTINUOUS_OHLCV_BUILD_AUDIT_SQL,
    )

    assert "CREATE TABLE IF NOT EXISTS ops.continuous_ohlcv_build_audit" in (
        CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    )
    assert "run_id TEXT PRIMARY KEY" in CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    assert "series_id TEXT NOT NULL" in CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    assert "timeframe TEXT NULL" in CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    assert "status TEXT NOT NULL" in CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    assert "row_count integer NOT NULL DEFAULT 0" in CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    assert "gap_count integer NOT NULL DEFAULT 0" in CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    assert "segment_count integer NOT NULL DEFAULT 0" in (
        CONTINUOUS_OHLCV_BUILD_AUDIT_SQL
    )
    assert "core.continuous_ohlcv_default" in CONTINUOUS_OHLCV_BUILD_AUDIT_SQL


def test_continuous_build_audit_migration_registered_after_identity_audit() -> None:
    from src.db.migration_registry import get_migrations

    migration_ids = [migration.id for migration in get_migrations()]

    assert "530_continuous_ohlcv_build_audit" in migration_ids
    assert migration_ids.index(
        "530_continuous_ohlcv_build_audit"
    ) > migration_ids.index("520_series_identity_build_audit")
