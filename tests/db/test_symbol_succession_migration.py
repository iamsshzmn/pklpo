from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED_SQL = ROOT / "scripts" / "seed_ops_symbol_succession_ton_gram.sql"
CHECKS_SQL = ROOT / "scripts" / "symbol_succession_ton_gram_checks.sql"


def test_symbol_succession_migration_schema_contract() -> None:
    from src.db.migrations.migrate_create_ops_symbol_succession import (
        SYMBOL_SUCCESSION_EVENT_TYPES,
        SYMBOL_SUCCESSION_SQL,
        SYMBOL_SUCCESSION_STATEMENTS,
        SYMBOL_SUCCESSION_STATUSES,
    )

    assert len(SYMBOL_SUCCESSION_STATEMENTS) == 4
    assert "\n\n".join(SYMBOL_SUCCESSION_STATEMENTS) == SYMBOL_SUCCESSION_SQL
    assert SYMBOL_SUCCESSION_STATUSES == ("needs_review", "approved", "rejected")
    assert SYMBOL_SUCCESSION_EVENT_TYPES == (
        "ticker_change",
        "token_migration",
        "redenomination",
        "delisting",
        "relisting",
        "contract_upgrade",
        "hard_fork",
        "merge",
        "split",
    )
    assert "CREATE SCHEMA IF NOT EXISTS ops" in SYMBOL_SUCCESSION_SQL
    assert "CREATE TABLE IF NOT EXISTS ops.symbol_succession" in (SYMBOL_SUCCESSION_SQL)
    assert "old_symbol               text        NOT NULL" in SYMBOL_SUCCESSION_SQL
    assert "new_symbol               text        NOT NULL" in SYMBOL_SUCCESSION_SQL
    assert "venue                    text        NOT NULL DEFAULT 'OKX'" in (
        SYMBOL_SUCCESSION_SQL
    )
    assert "ratio                    numeric     NOT NULL DEFAULT 1" in (
        SYMBOL_SUCCESSION_SQL
    )
    assert "notes                    jsonb       NOT NULL DEFAULT '{}'::jsonb" in (
        SYMBOL_SUCCESSION_SQL
    )
    assert "PRIMARY KEY (venue, inst_type, old_symbol, new_symbol)" in (
        SYMBOL_SUCCESSION_SQL
    )
    assert "CONSTRAINT chk_symbol_succession_status" in SYMBOL_SUCCESSION_SQL
    assert "CONSTRAINT chk_symbol_succession_ratio_positive CHECK (ratio > 0)" in (
        SYMBOL_SUCCESSION_SQL
    )
    assert "CONSTRAINT chk_symbol_succession_event_type CHECK" in (
        SYMBOL_SUCCESSION_SQL
    )
    assert "CREATE INDEX IF NOT EXISTS ix_symbol_succession_new_symbol" in (
        SYMBOL_SUCCESSION_SQL
    )
    assert "CREATE INDEX IF NOT EXISTS ix_symbol_succession_status" in (
        SYMBOL_SUCCESSION_SQL
    )
    for status in SYMBOL_SUCCESSION_STATUSES:
        assert f"'{status}'" in SYMBOL_SUCCESSION_SQL
    for event_type in SYMBOL_SUCCESSION_EVENT_TYPES:
        assert f"'{event_type}'" in SYMBOL_SUCCESSION_SQL


def test_symbol_succession_migration_registered_after_470() -> None:
    from src.db.migration_registry import get_migrations

    migrations = get_migrations()
    ids = [migration.id for migration in migrations]
    idx_470 = ids.index("470_ops_recovery_symbol_discovery")

    assert ids[idx_470 + 1] == "480_ops_symbol_succession"
    assert len(ids) == len(set(ids))


def test_ton_gram_seed_sql_is_idempotent_needs_review() -> None:
    sql = SEED_SQL.read_text(encoding="utf-8")

    assert "INSERT INTO ops.symbol_succession" in sql
    assert "TON-USDT-SWAP" in sql
    assert "GRAM-USDT-SWAP" in sql
    assert "'SWAP'" in sql
    assert "'OKX'" in sql
    assert "'token_migration'" in sql
    assert "'needs_review'" in sql
    assert "'https://www.okx.com/help/okx-to-support-ton-crypto-migration'" in sql
    assert "ON CONFLICT (venue, inst_type, old_symbol, new_symbol) DO NOTHING" in sql
    assert "tick/lot checked against OKX announcement, not DB" in sql


def test_ton_gram_checks_sql_reports_specs_and_continuity_without_approval() -> None:
    sql = CHECKS_SQL.read_text(encoding="utf-8")

    assert "specs_match" in sql
    assert "continuity_ok" in sql
    assert "ct_val IS NOT DISTINCT FROM" in sql
    assert "ct_type IS NOT DISTINCT FROM" in sql
    assert "ct_val_ccy IS NOT DISTINCT FROM" in sql
    assert "settle_ccy IS NOT DISTINCT FROM" in sql
    assert "min_sz IS NOT DISTINCT FROM" in sql
    assert "min(timestamp)" in sql
    assert "max(timestamp)" in sql
    assert "symbol='TON-USDT-SWAP'" in sql
    assert "symbol='GRAM-USDT-SWAP'" in sql
    assert "-- UPDATE ops.symbol_succession SET status='approved'" in sql
    assert "UPDATE ops.symbol_succession SET status='approved'" not in "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
