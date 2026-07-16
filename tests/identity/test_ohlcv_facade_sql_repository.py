from __future__ import annotations


def test_ohlcv_facade_sql_repository_contract_queries_identity_layers() -> None:
    from src.identity.infrastructure.ohlcv_facade_repository import (
        GET_ADJUSTMENT_FACTOR_SQL,
        GET_SERIES_KIND_SQL,
        READ_CONTINUOUS_SQL,
        READ_GAP_MARKERS_SQL,
        READ_RAW_SQL,
        RESOLVE_ALIAS_SQL,
    )

    assert "FROM core.series_alias" in RESOLVE_ALIAS_SQL
    assert "old_series_id = :series_id" in RESOLVE_ALIAS_SQL
    assert "known_from <= :as_of" in RESOLVE_ALIAS_SQL
    assert "known_to IS NULL OR known_to > :as_of" in RESOLVE_ALIAS_SQL

    assert "FROM core.series_registry" in GET_SERIES_KIND_SQL
    assert "series_id = :series_id" in GET_SERIES_KIND_SQL

    assert "FROM public.swap_ohlcv_p" in READ_RAW_SQL
    assert "symbol = :series_id" in READ_RAW_SQL
    assert "bar_kind" in READ_RAW_SQL
    assert "succession_id" in READ_RAW_SQL

    assert "FROM core.continuous_ohlcv_p" in READ_CONTINUOUS_SQL
    assert "series_id = :series_id" in READ_CONTINUOUS_SQL
    assert "ORDER BY timestamp" in READ_CONTINUOUS_SQL

    assert "FROM core.series_gap_ranges" in READ_GAP_MARKERS_SQL
    assert "gap_start_ts < CAST(:end_ts AS bigint)" in READ_GAP_MARKERS_SQL
    assert "gap_end_ts > CAST(:start_ts AS bigint)" in READ_GAP_MARKERS_SQL
    assert "known_from <= :as_of" in READ_GAP_MARKERS_SQL

    assert "FROM core.series_adjustments" in GET_ADJUSTMENT_FACTOR_SQL
    assert "effective_ts <= CAST(:timestamp AS bigint)" in GET_ADJUSTMENT_FACTOR_SQL
    assert "known_from <= :as_of" in GET_ADJUSTMENT_FACTOR_SQL
