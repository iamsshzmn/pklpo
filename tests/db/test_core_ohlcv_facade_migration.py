from __future__ import annotations


def test_core_ohlcv_facade_migration_contract() -> None:
    from src.db.migrations.migrate_create_core_ohlcv_facade import (
        CORE_OHLCV_FACADE_SQL,
        CORE_OHLCV_FACADE_STATEMENTS,
    )

    assert len(CORE_OHLCV_FACADE_STATEMENTS) >= 4
    assert ";\n\n".join(CORE_OHLCV_FACADE_STATEMENTS) + ";" == CORE_OHLCV_FACADE_SQL

    assert "CREATE SCHEMA IF NOT EXISTS core" in CORE_OHLCV_FACADE_SQL

    # PIT function contract: same read contract as the code facade (§12.3 output schema).
    assert "CREATE OR REPLACE FUNCTION core.f_ohlcv_pit(" in CORE_OHLCV_FACADE_SQL
    assert "p_series_id text" in CORE_OHLCV_FACADE_SQL
    assert "p_timeframe text" in CORE_OHLCV_FACADE_SQL
    assert "p_start_ts bigint" in CORE_OHLCV_FACADE_SQL
    assert "p_end_ts bigint" in CORE_OHLCV_FACADE_SQL
    assert "p_as_of timestamptz DEFAULT NULL" in CORE_OHLCV_FACADE_SQL
    assert "p_include_gap_markers boolean DEFAULT false" in CORE_OHLCV_FACADE_SQL

    for column in (
        "series_id text",
        "timeframe text",
        "timestamp bigint",
        "open numeric",
        "high numeric",
        "low numeric",
        "close numeric",
        "volume numeric",
        "segment_id text",
        "source_venue text",
        "source_symbol text",
        "source_timestamp bigint",
        "bar_kind text",
        "data_status text",
        "succession_id text",
        "adjustment_factor numeric",
        "is_gap boolean",
        "gap_type text",
    ):
        assert column in CORE_OHLCV_FACADE_SQL

    # PIT alias resolution mirrors src.identity.infrastructure.ohlcv_facade_repository.
    assert "FROM core.series_alias a" in CORE_OHLCV_FACADE_SQL
    assert "a.old_series_id = p_series_id" in CORE_OHLCV_FACADE_SQL
    assert "a.known_from <= v_as_of" in CORE_OHLCV_FACADE_SQL
    assert "a.known_to IS NULL OR a.known_to > v_as_of" in CORE_OHLCV_FACADE_SQL

    # series_kind lookup defaults to trivial passthrough when unregistered.
    assert "FROM core.series_registry r" in CORE_OHLCV_FACADE_SQL
    assert (
        "v_series_kind := COALESCE(v_series_kind, 'trivial')" in CORE_OHLCV_FACADE_SQL
    )

    # Trivial passthrough is raw, unadjusted-lineage: bar_kind='native', factor=1 default.
    assert "FROM public.swap_ohlcv_p o" in CORE_OHLCV_FACADE_SQL
    assert "WHERE v_series_kind <> 'composite'" in CORE_OHLCV_FACADE_SQL
    assert "'native'::text AS bar_kind" in CORE_OHLCV_FACADE_SQL
    assert "'complete'::text AS data_status" in CORE_OHLCV_FACADE_SQL

    # Composite series read only from the materialized continuous table.
    assert "FROM core.continuous_ohlcv_p c" in CORE_OHLCV_FACADE_SQL
    assert "WHERE v_series_kind = 'composite'" in CORE_OHLCV_FACADE_SQL

    # Gap markers are output-only, gated by p_include_gap_markers, never physical rows.
    assert "FROM core.series_gap_ranges g" in CORE_OHLCV_FACADE_SQL
    assert "WHERE p_include_gap_markers" in CORE_OHLCV_FACADE_SQL
    assert "'gap_marker'::text AS bar_kind" in CORE_OHLCV_FACADE_SQL
    assert "'missing'::text AS data_status" in CORE_OHLCV_FACADE_SQL

    # PIT adjustment factor lookup mirrors GET_ADJUSTMENT_FACTOR_SQL; volume untouched.
    assert "FROM core.series_adjustments a" in CORE_OHLCV_FACADE_SQL
    assert "a.effective_ts <= r.timestamp" in CORE_OHLCV_FACADE_SQL
    assert "r.open * adj.factor" in CORE_OHLCV_FACADE_SQL
    assert "r.high * adj.factor" in CORE_OHLCV_FACADE_SQL
    assert "r.low * adj.factor" in CORE_OHLCV_FACADE_SQL
    assert "r.close * adj.factor" in CORE_OHLCV_FACADE_SQL
    assert "r.volume," in CORE_OHLCV_FACADE_SQL

    # Gap markers sort before the real bar at the same timestamp (matches OhlcvFacade sort key).
    assert "ORDER BY r.timestamp, r.is_gap DESC" in CORE_OHLCV_FACADE_SQL

    # BI/SQL security_barrier view, built on the same PIT function for the current snapshot.
    assert "CREATE OR REPLACE VIEW core.v_ohlcv_facade" in CORE_OHLCV_FACADE_SQL
    assert "WITH (security_barrier = true) AS" in CORE_OHLCV_FACADE_SQL
    assert "CROSS JOIN LATERAL core.f_ohlcv_pit(" in CORE_OHLCV_FACADE_SQL
    assert "series_kind = 'composite'" in CORE_OHLCV_FACADE_SQL

    assert "COMMENT ON FUNCTION core.f_ohlcv_pit(" in CORE_OHLCV_FACADE_SQL
    assert "COMMENT ON VIEW core.v_ohlcv_facade" in CORE_OHLCV_FACADE_SQL


def test_core_ohlcv_facade_migration_registered_after_continuous_build_audit() -> None:
    from src.db.migration_registry import get_migrations

    migration_ids = [migration.id for migration in get_migrations()]

    assert "540_core_ohlcv_facade" in migration_ids
    assert len(migration_ids) == len(set(migration_ids))
    assert migration_ids.index("540_core_ohlcv_facade") > migration_ids.index(
        "530_continuous_ohlcv_build_audit"
    )
