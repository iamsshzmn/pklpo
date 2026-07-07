from __future__ import annotations


def test_recovery_symbol_discovery_migration_schema_contract() -> None:
    from src.db.migrations.migrate_create_ops_recovery_symbol_discovery import (
        RECOVERY_SYMBOL_DISCOVERY_SQL,
        RECOVERY_SYMBOL_DISCOVERY_STATEMENTS,
        RECOVERY_SYMBOL_DISCOVERY_STATUSES,
    )

    assert len(RECOVERY_SYMBOL_DISCOVERY_STATEMENTS) == 3
    assert "\n\n".join(RECOVERY_SYMBOL_DISCOVERY_STATEMENTS) == (
        RECOVERY_SYMBOL_DISCOVERY_SQL
    )
    assert RECOVERY_SYMBOL_DISCOVERY_STATUSES == ("active", "closed")
    assert "CREATE SCHEMA IF NOT EXISTS ops" in RECOVERY_SYMBOL_DISCOVERY_SQL
    assert "CREATE TABLE IF NOT EXISTS ops.recovery_symbol_discovery" in (
        RECOVERY_SYMBOL_DISCOVERY_SQL
    )
    assert "symbol        TEXT        PRIMARY KEY" in RECOVERY_SYMBOL_DISCOVERY_SQL
    assert "reason        TEXT        NOT NULL" in RECOVERY_SYMBOL_DISCOVERY_SQL
    assert "status        TEXT        NOT NULL DEFAULT 'active'" in (
        RECOVERY_SYMBOL_DISCOVERY_SQL
    )
    assert "closed_at     TIMESTAMPTZ" in RECOVERY_SYMBOL_DISCOVERY_SQL
    assert "closed_reason TEXT" in RECOVERY_SYMBOL_DISCOVERY_SQL
    assert "CONSTRAINT chk_recovery_symbol_discovery_status CHECK" in (
        RECOVERY_SYMBOL_DISCOVERY_SQL
    )
    assert "CREATE INDEX IF NOT EXISTS ix_recovery_symbol_discovery_status" in (
        RECOVERY_SYMBOL_DISCOVERY_SQL
    )
    for status in RECOVERY_SYMBOL_DISCOVERY_STATUSES:
        assert f"'{status}'" in RECOVERY_SYMBOL_DISCOVERY_SQL


def test_recovery_symbol_discovery_migration_registered_after_460() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]
    idx_460 = ids.index("460_allow_candidate_pipeline_recovery_decisions")

    assert ids[idx_460 + 1] == "470_ops_recovery_symbol_discovery"
    assert len(ids) == len(set(ids))
