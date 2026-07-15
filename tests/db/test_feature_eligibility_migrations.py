from __future__ import annotations


def test_feature_eligibility_migration_creates_state_table_contract() -> None:
    from src.db.migrations.migrate_create_ops_feature_eligibility import (
        FEATURE_ELIGIBILITY_STATES,
        FEATURE_ELIGIBILITY_TABLE_SQL,
    )

    assert FEATURE_ELIGIBILITY_STATES == (
        "eligible",
        "insufficient_history",
        "incomplete_history",
        "invalid_history",
        "informational_only",
        "disabled",
    )
    assert "CREATE SCHEMA IF NOT EXISTS ops" in FEATURE_ELIGIBILITY_TABLE_SQL
    assert "CREATE TABLE IF NOT EXISTS ops.feature_eligibility" in (
        FEATURE_ELIGIBILITY_TABLE_SQL
    )
    assert "PRIMARY KEY (symbol, timeframe)" in FEATURE_ELIGIBILITY_TABLE_SQL
    assert "CONSTRAINT chk_fe_state CHECK" in FEATURE_ELIGIBILITY_TABLE_SQL
    for state in FEATURE_ELIGIBILITY_STATES:
        assert f"'{state}'" in FEATURE_ELIGIBILITY_TABLE_SQL
    assert "CREATE INDEX IF NOT EXISTS ix_fe_state" in FEATURE_ELIGIBILITY_TABLE_SQL
    assert "CREATE INDEX IF NOT EXISTS ix_fe_evaluated" in FEATURE_ELIGIBILITY_TABLE_SQL


def test_feature_eligibility_transitions_migration_creates_audit_contract() -> None:
    from src.db.migrations.migrate_create_ops_feature_eligibility_transitions import (
        FEATURE_ELIGIBILITY_TRANSITIONS_SQL,
    )

    assert "CREATE SCHEMA IF NOT EXISTS ops" in FEATURE_ELIGIBILITY_TRANSITIONS_SQL
    assert "CREATE TABLE IF NOT EXISTS ops.feature_eligibility_transitions" in (
        FEATURE_ELIGIBILITY_TRANSITIONS_SQL
    )
    assert "id                BIGSERIAL PRIMARY KEY" in (
        FEATURE_ELIGIBILITY_TRANSITIONS_SQL
    )
    assert "from_state        TEXT" in FEATURE_ELIGIBILITY_TRANSITIONS_SQL
    assert (
        "to_state          TEXT        NOT NULL" in FEATURE_ELIGIBILITY_TRANSITIONS_SQL
    )
    assert "CREATE INDEX IF NOT EXISTS ix_fet_occurred" in (
        FEATURE_ELIGIBILITY_TRANSITIONS_SQL
    )
    assert "CREATE INDEX IF NOT EXISTS ix_fet_symbol" in (
        FEATURE_ELIGIBILITY_TRANSITIONS_SQL
    )


def test_feature_eligibility_migrations_are_registered_after_410() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]
    idx_410 = ids.index("410_retention_horizon_guard")

    assert ids[idx_410 + 1] == "420_ops_feature_eligibility"
    assert ids[idx_410 + 2] == "430_ops_feature_eligibility_transitions"
