from __future__ import annotations


def test_execution_resolver_sql_repository_contract_queries_identity_layers() -> None:
    from src.identity.infrastructure.execution_resolver_repository import (
        FIND_ACTIVE_MEMBER_SQL,
        RESOLVE_ALIAS_SQL,
    )

    assert "FROM core.series_alias" in RESOLVE_ALIAS_SQL
    assert "old_series_id = :series_id" in RESOLVE_ALIAS_SQL
    assert "known_from <= :as_of" in RESOLVE_ALIAS_SQL
    assert "known_to IS NULL OR known_to > :as_of" in RESOLVE_ALIAS_SQL

    assert "FROM core.series_members m" in FIND_ACTIVE_MEMBER_SQL
    assert "LEFT JOIN public.instruments i ON i.symbol = m.source_symbol" in (
        FIND_ACTIVE_MEMBER_SQL
    )
    assert "m.series_id = :series_id" in FIND_ACTIVE_MEMBER_SQL

    # Market-time validity window (valid_from/valid_to, epoch ms) — this is what
    # must decide the resolved leg, not "last source_symbol in continuous history".
    assert "m.valid_from <= CAST(:as_of_ms AS bigint)" in FIND_ACTIVE_MEMBER_SQL
    assert (
        "m.valid_to IS NULL OR m.valid_to > CAST(:as_of_ms AS bigint)"
        in FIND_ACTIVE_MEMBER_SQL
    )

    # PIT knowledge window uses the same as_of as the market-time window (no
    # separate "know everything now" shortcut that would leak future knowledge
    # into a historical backtest replay).
    assert "m.known_from <= :as_of" in FIND_ACTIVE_MEMBER_SQL
    assert "m.known_to IS NULL OR m.known_to > :as_of" in FIND_ACTIVE_MEMBER_SQL

    assert "i.state AS instrument_state" in FIND_ACTIVE_MEMBER_SQL
    assert "ORDER BY m.valid_from DESC, m.known_from DESC" in FIND_ACTIVE_MEMBER_SQL
    assert "LIMIT 1" in FIND_ACTIVE_MEMBER_SQL
