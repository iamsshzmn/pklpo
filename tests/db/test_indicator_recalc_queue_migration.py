from __future__ import annotations


def test_indicator_recalc_queue_migration_creates_claimable_queue_contract() -> None:
    from src.db.migrations.migrate_create_ops_indicator_recalc_queue import (
        INDICATOR_RECALC_QUEUE_SQL,
        INDICATOR_RECALC_QUEUE_STATUSES,
    )

    assert INDICATOR_RECALC_QUEUE_STATUSES == (
        "queued",
        "claimed",
        "completed",
        "blocked",
        "failed",
    )
    assert "CREATE SCHEMA IF NOT EXISTS ops" in INDICATOR_RECALC_QUEUE_SQL
    assert "CREATE TABLE IF NOT EXISTS ops.indicator_recalc_queue" in (
        INDICATOR_RECALC_QUEUE_SQL
    )
    assert "range_start_ts" in INDICATOR_RECALC_QUEUE_SQL
    assert "range_end_ts" in INDICATOR_RECALC_QUEUE_SQL
    assert "warmup_bars" in INDICATOR_RECALC_QUEUE_SQL
    assert "claimed_at" in INDICATOR_RECALC_QUEUE_SQL
    assert "completed_at" in INDICATOR_RECALC_QUEUE_SQL
    assert "source_dag" in INDICATOR_RECALC_QUEUE_SQL
    assert "chk_irq_status" in INDICATOR_RECALC_QUEUE_SQL
    assert "uq_irq_symbol_tf_range" in INDICATOR_RECALC_QUEUE_SQL
    assert "ix_irq_claim" in INDICATOR_RECALC_QUEUE_SQL


def test_indicator_recalc_queue_migration_registered_after_430() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]

    assert ids[ids.index("430_ops_feature_eligibility_transitions") + 1] == (
        "440_ops_indicator_recalc_queue"
    )


def test_indicator_recalc_queue_migration_executes_single_ddl_statements() -> None:
    from src.db.migrations.migrate_create_ops_indicator_recalc_queue import (
        INDICATOR_RECALC_QUEUE_STATEMENTS,
    )

    assert len(INDICATOR_RECALC_QUEUE_STATEMENTS) == 4
    assert all(statement.strip() for statement in INDICATOR_RECALC_QUEUE_STATEMENTS)
    assert all(";" not in statement for statement in INDICATOR_RECALC_QUEUE_STATEMENTS)
