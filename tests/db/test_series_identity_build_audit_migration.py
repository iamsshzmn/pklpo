from __future__ import annotations


def test_series_identity_build_audit_migration_schema_contract() -> None:
    from src.db.migrations.migrate_create_series_identity_build_audit import (
        SERIES_IDENTITY_BUILD_AUDIT_SQL,
        SERIES_IDENTITY_BUILD_AUDIT_STATEMENTS,
        SERIES_IDENTITY_BUILD_STATUSES,
    )

    assert len(SERIES_IDENTITY_BUILD_AUDIT_STATEMENTS) == 4
    assert ";\n\n".join(SERIES_IDENTITY_BUILD_AUDIT_STATEMENTS) + ";" == (
        SERIES_IDENTITY_BUILD_AUDIT_SQL
    )
    assert "CREATE SCHEMA IF NOT EXISTS ops" in SERIES_IDENTITY_BUILD_AUDIT_SQL
    assert "CREATE TABLE IF NOT EXISTS ops.series_identity_build_audit" in (
        SERIES_IDENTITY_BUILD_AUDIT_SQL
    )
    for column in (
        "run_id TEXT PRIMARY KEY",
        "algo_version TEXT NOT NULL",
        "params_hash TEXT NOT NULL",
        "snapshot_id TEXT NULL",
        "started_at timestamptz NOT NULL",
        "finished_at timestamptz NULL",
        "status TEXT NOT NULL",
        "input_hash TEXT NOT NULL",
        "rows_inserted integer NOT NULL DEFAULT 0",
        "rows_deleted integer NOT NULL DEFAULT 0",
        "gap_count integer NOT NULL DEFAULT 0",
        "segment_count integer NOT NULL DEFAULT 0",
        "error_type TEXT NULL",
        "error_message_hash TEXT NULL",
    ):
        assert column in SERIES_IDENTITY_BUILD_AUDIT_SQL
    assert "chk_series_identity_build_audit_status" in (
        SERIES_IDENTITY_BUILD_AUDIT_SQL
    )
    assert "ix_series_identity_build_audit_status_started" in (
        SERIES_IDENTITY_BUILD_AUDIT_SQL
    )
    assert "ix_series_identity_build_audit_finished" in (
        SERIES_IDENTITY_BUILD_AUDIT_SQL
    )
    assert SERIES_IDENTITY_BUILD_STATUSES == ("running", "success", "failed")


def test_series_identity_build_audit_migration_registered_after_510() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]
    idx_510 = ids.index("510_core_identity")

    assert ids[idx_510 + 1] == "520_series_identity_build_audit"
    assert len(ids) == len(set(ids))
