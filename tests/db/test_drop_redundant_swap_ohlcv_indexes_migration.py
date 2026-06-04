from __future__ import annotations


def test_drop_redundant_swap_ohlcv_indexes_verifies_expected_index_shape() -> None:
    from src.db.migrations.migrate_drop_redundant_swap_ohlcv_indexes import (
        DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL,
        REDUNDANT_SWAP_OHLCV_INDEXES,
    )

    assert REDUNDANT_SWAP_OHLCV_INDEXES == (
        "idx_swap_ohlcv_p_symbol_timeframe_timestamp",
        "idx_swap_ohlcv_p_lookup",
    )
    assert "pg_index" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indisprimary IS FALSE" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indnkeyatts = 3" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indpred IS NULL" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "indexprs IS NULL" in DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    assert "DROP INDEX IF EXISTS idx_swap_ohlcv_p_symbol_timeframe_timestamp" in (
        DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    )
    assert "DROP INDEX IF EXISTS idx_swap_ohlcv_p_lookup" in (
        DROP_REDUNDANT_SWAP_OHLCV_INDEXES_SQL
    )


def test_drop_redundant_swap_ohlcv_indexes_migration_is_registered_after_390() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]

    assert ids[ids.index("390_research_tf_infinite_retention") + 1] == (
        "400_drop_redundant_swap_ohlcv_indexes"
    )
