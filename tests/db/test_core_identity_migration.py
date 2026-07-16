from __future__ import annotations


def test_core_identity_migration_schema_contract() -> None:
    from src.db.migrations.migrate_create_core_identity import (
        CORE_IDENTITY_SQL,
        CORE_IDENTITY_STATEMENTS,
        SERIES_DATA_STATUSES,
        SERIES_GAP_TYPES,
        SERIES_KINDS,
        SERIES_STATUSES,
    )

    assert len(CORE_IDENTITY_STATEMENTS) >= 12
    assert ";\n\n".join(CORE_IDENTITY_STATEMENTS) + ";" == CORE_IDENTITY_SQL

    assert "CREATE SCHEMA IF NOT EXISTS core" in CORE_IDENTITY_SQL
    for table_name in (
        "core.series_registry",
        "core.series_members",
        "core.series_alias",
        "core.series_segments",
        "core.series_gap_ranges",
        "core.series_adjustments",
        "core.continuous_ohlcv_p",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in CORE_IDENTITY_SQL

    assert "series_id TEXT PRIMARY KEY" in CORE_IDENTITY_SQL
    assert "series_label TEXT NOT NULL" in CORE_IDENTITY_SQL
    assert "asset_id TEXT NULL" in CORE_IDENTITY_SQL
    assert "CHECK (series_kind IN ('trivial','composite'))" in CORE_IDENTITY_SQL
    assert "CHECK (status IN ('active','retired','superseded'))" in CORE_IDENTITY_SQL

    assert "source_venue TEXT NOT NULL" in CORE_IDENTITY_SQL
    assert "source_symbol TEXT NOT NULL" in CORE_IDENTITY_SQL
    assert "known_from timestamptz NOT NULL" in CORE_IDENTITY_SQL
    assert "known_to timestamptz NULL" in CORE_IDENTITY_SQL
    assert "adjustment_factor NUMERIC NOT NULL DEFAULT 1" in CORE_IDENTITY_SQL
    assert "CHECK (adjustment_factor > 0)" in CORE_IDENTITY_SQL
    assert "CHECK (valid_to IS NULL OR valid_from < valid_to)" in CORE_IDENTITY_SQL
    assert "CHECK (known_to IS NULL OR known_from < known_to)" in CORE_IDENTITY_SQL
    assert (
        "PRIMARY KEY (series_id, source_venue, source_symbol, valid_from, known_from)"
        in CORE_IDENTITY_SQL
    )

    assert (
        "PRIMARY KEY (old_series_id, canonical_series_id, known_from)"
        in CORE_IDENTITY_SQL
    )
    assert (
        "PRIMARY KEY (series_id, timeframe, segment_id, known_from)"
        in CORE_IDENTITY_SQL
    )
    assert (
        "PRIMARY KEY (series_id, timeframe, gap_start_ts, gap_end_ts, gap_type, known_from)"
        in CORE_IDENTITY_SQL
    )
    assert "CHECK (gap_start_ts < gap_end_ts)" in CORE_IDENTITY_SQL
    assert "CHECK (gap_type IN (" in CORE_IDENTITY_SQL

    assert "CREATE TABLE IF NOT EXISTS core.continuous_ohlcv_p" in CORE_IDENTITY_SQL
    assert "PARTITION BY RANGE (timestamp)" in CORE_IDENTITY_SQL
    assert "bar_kind TEXT NOT NULL" in CORE_IDENTITY_SQL
    assert "CHECK (bar_kind IN ('native','synthetic'))" in CORE_IDENTITY_SQL
    assert "gap_marker" not in CORE_IDENTITY_SQL
    assert "adjusted" not in CORE_IDENTITY_SQL
    assert "PRIMARY KEY (series_id, timeframe, timestamp)" in CORE_IDENTITY_SQL
    assert "run_id TEXT NOT NULL" in CORE_IDENTITY_SQL
    assert "algo_version TEXT NOT NULL" in CORE_IDENTITY_SQL
    assert "params_hash TEXT NOT NULL" in CORE_IDENTITY_SQL
    assert "snapshot_id TEXT NULL" in CORE_IDENTITY_SQL

    for index_name in (
        "ix_series_members_series_range",
        "ix_series_members_source_range",
        "ix_series_gap_ranges_series_range",
        "ix_series_segments_series_range",
        "ix_continuous_ohlcv_source_lookup",
        "ix_continuous_ohlcv_succession",
    ):
        assert f"CREATE INDEX IF NOT EXISTS {index_name}" in CORE_IDENTITY_SQL

    assert SERIES_KINDS == ("trivial", "composite")
    assert SERIES_STATUSES == ("active", "retired", "superseded")
    assert SERIES_GAP_TYPES == (
        "unknown_raw_gap",
        "migration_halt",
        "market_halt",
        "recoverable_data_gap",
    )
    assert SERIES_DATA_STATUSES == (
        "complete",
        "partial",
        "missing",
        "invalid",
        "warmup",
    )


def test_core_identity_migration_registered_after_500() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]
    idx_500 = ids.index("500_ops_identity_inputs")

    assert ids[idx_500 + 1] == "510_core_identity"
    assert len(ids) == len(set(ids))
