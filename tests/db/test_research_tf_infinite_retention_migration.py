from __future__ import annotations


def test_research_tf_infinite_retention_sql_only_updates_active_research_tfs() -> None:
    from src.db.migrations.migrate_set_research_tf_infinite_retention import (
        RESEARCH_TF_INFINITE_RETENTION_SQL,
        RESEARCH_TIMEFRAMES,
    )

    assert RESEARCH_TIMEFRAMES == ("1H", "4H", "1D")
    assert "SET retention_days = NULL" in RESEARCH_TF_INFINITE_RETENTION_SQL
    assert "WHERE timeframe IN ('1H', '4H', '1D')" in RESEARCH_TF_INFINITE_RETENTION_SQL
    assert "'1W'" not in RESEARCH_TF_INFINITE_RETENTION_SQL
    assert "'1M'" not in RESEARCH_TF_INFINITE_RETENTION_SQL
    assert "'1m'" not in RESEARCH_TF_INFINITE_RETENTION_SQL
    assert "'5m'" not in RESEARCH_TF_INFINITE_RETENTION_SQL
    assert "'15m'" not in RESEARCH_TF_INFINITE_RETENTION_SQL
    assert "'30m'" not in RESEARCH_TF_INFINITE_RETENTION_SQL


def test_research_tf_infinite_retention_migration_is_registered_after_380() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]

    assert ids[ids.index("380_swap_ohlcv_alignment_trigger") + 1] == (
        "390_research_tf_infinite_retention"
    )
