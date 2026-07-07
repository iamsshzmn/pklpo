from __future__ import annotations


def test_ops_identity_inputs_migration_schema_contract() -> None:
    from src.db.migrations.migrate_extend_ops_identity_inputs import (
        GAP_CLASSIFICATION_SQL,
        GAP_CLASSIFICATION_STATUSES,
        GAP_CLASSIFICATION_TYPES,
        OPS_IDENTITY_INPUTS_SQL,
        OPS_IDENTITY_INPUTS_STATEMENTS,
        SYMBOL_SUCCESSION_PIT_SQL,
    )

    assert len(OPS_IDENTITY_INPUTS_STATEMENTS) >= 10
    assert ";\n\n".join(OPS_IDENTITY_INPUTS_STATEMENTS) + ";" == (
        OPS_IDENTITY_INPUTS_SQL
    )

    assert "ALTER TABLE ops.symbol_succession" in SYMBOL_SUCCESSION_PIT_SQL
    assert "ADD COLUMN IF NOT EXISTS effective_from timestamptz NULL" in (
        SYMBOL_SUCCESSION_PIT_SQL
    )
    assert "ADD COLUMN IF NOT EXISTS known_from timestamptz NOT NULL DEFAULT now()" in (
        SYMBOL_SUCCESSION_PIT_SQL
    )
    assert "ADD COLUMN IF NOT EXISTS approved_at timestamptz NULL" in (
        SYMBOL_SUCCESSION_PIT_SQL
    )
    assert "chk_symbol_succession_approved_at" in SYMBOL_SUCCESSION_PIT_SQL
    assert "chk_symbol_succession_effective_from" in SYMBOL_SUCCESSION_PIT_SQL
    assert "chk_symbol_succession_known_before_approved" in (
        SYMBOL_SUCCESSION_PIT_SQL
    )
    assert "ix_symbol_succession_status_approved_at" in (
        SYMBOL_SUCCESSION_PIT_SQL
    )
    assert "ix_symbol_succession_build_lookup" in SYMBOL_SUCCESSION_PIT_SQL
    assert "ix_symbol_succession_new_symbol_known" in SYMBOL_SUCCESSION_PIT_SQL

    assert "CREATE TABLE IF NOT EXISTS ops.gap_classification" in (
        GAP_CLASSIFICATION_SQL
    )
    assert "id              bigserial   PRIMARY KEY" in GAP_CLASSIFICATION_SQL
    assert "series_id       text        NOT NULL" in GAP_CLASSIFICATION_SQL
    assert "timeframe       text        NULL" in GAP_CLASSIFICATION_SQL
    assert "range_start_ts  bigint      NOT NULL" in GAP_CLASSIFICATION_SQL
    assert "range_end_ts    bigint      NOT NULL" in GAP_CLASSIFICATION_SQL
    assert "gap_type        text        NOT NULL" in GAP_CLASSIFICATION_SQL
    assert "recoverability  text        NOT NULL DEFAULT 'unknown'" in (
        GAP_CLASSIFICATION_SQL
    )
    assert "evidence        jsonb       NOT NULL DEFAULT '{}'::jsonb" in (
        GAP_CLASSIFICATION_SQL
    )
    assert "asserted_by     text        NOT NULL" in GAP_CLASSIFICATION_SQL
    assert "status          text        NOT NULL DEFAULT 'needs_review'" in (
        GAP_CLASSIFICATION_SQL
    )
    assert "known_from      timestamptz NOT NULL DEFAULT now()" in (
        GAP_CLASSIFICATION_SQL
    )
    assert "approved_at     timestamptz NULL" in GAP_CLASSIFICATION_SQL
    assert "chk_gap_classification_range" in GAP_CLASSIFICATION_SQL
    assert "chk_gap_classification_type" in GAP_CLASSIFICATION_SQL
    assert "chk_gap_classification_status" in GAP_CLASSIFICATION_SQL
    assert "chk_gap_classification_approved_at" in GAP_CLASSIFICATION_SQL
    assert "chk_gap_classification_known_before_approved" in (
        GAP_CLASSIFICATION_SQL
    )
    assert "ux_gap_classification_identity" in GAP_CLASSIFICATION_SQL
    assert "COALESCE(timeframe, '*')" in GAP_CLASSIFICATION_SQL
    assert "ix_gap_classification_approved" in GAP_CLASSIFICATION_SQL

    assert GAP_CLASSIFICATION_TYPES == (
        "unknown_raw_gap",
        "migration_halt",
        "market_halt",
        "recoverable_data_gap",
    )
    assert GAP_CLASSIFICATION_STATUSES == (
        "needs_review",
        "approved",
        "rejected",
    )

    for gap_type in GAP_CLASSIFICATION_TYPES:
        assert f"'{gap_type}'" in GAP_CLASSIFICATION_SQL
    for status in GAP_CLASSIFICATION_STATUSES:
        assert f"'{status}'" in GAP_CLASSIFICATION_SQL


def test_ops_identity_inputs_migration_registered_after_490() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]
    idx_490 = ids.index("490_drop_ops_recovery_symbol_discovery")

    assert ids[idx_490 + 1] == "500_ops_identity_inputs"
    assert len(ids) == len(set(ids))
