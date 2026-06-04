from __future__ import annotations


def test_retention_horizon_guard_clamps_finite_cutoff_to_warmup_horizon() -> None:
    from src.db.migrations.migrate_retention_horizon_guard import (
        RETENTION_HORIZON_GUARD_SQL,
        WARMUP_HORIZON_BARS,
    )

    assert WARMUP_HORIZON_BARS == 500
    assert "CREATE OR REPLACE FUNCTION cleanup_old_swap_data" in RETENTION_HORIZON_GUARD_SQL
    assert "policy.retention_days IS NULL" in RETENTION_HORIZON_GUARD_SQL
    assert "skipped_reason := 'infinite_retention'" in RETENTION_HORIZON_GUARD_SQL
    assert "min_keep_ts" in RETENTION_HORIZON_GUARD_SQL
    assert "LEAST(retention_cutoff_ts, min_keep_ts)" in RETENTION_HORIZON_GUARD_SQL
    assert "WHEN '1m' THEN 60 * 1000" in RETENTION_HORIZON_GUARD_SQL
    assert "WHEN '30m' THEN 30 * 60 * 1000" in RETENTION_HORIZON_GUARD_SQL


def test_retention_horizon_guard_migration_is_registered_after_400() -> None:
    from src.db.migration_registry import get_migrations

    ids = [migration.id for migration in get_migrations()]

    assert ids[ids.index("400_drop_redundant_swap_ohlcv_indexes") + 1] == (
        "410_retention_horizon_guard"
    )
