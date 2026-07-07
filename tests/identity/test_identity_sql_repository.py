from __future__ import annotations

from datetime import UTC, datetime


def test_identity_sql_repository_converts_succession_timestamps_to_ms() -> None:
    from src.identity.infrastructure.repository import _timestamp_to_ms

    assert _timestamp_to_ms(None) is None
    assert _timestamp_to_ms(1781692200000) == 1781692200000
    assert (
        _timestamp_to_ms(datetime(2026, 6, 17, 10, 30, tzinfo=UTC))
        == 1781692200000
    )


def test_identity_sql_repository_queries_enforce_pit_filters() -> None:
    from src.identity.infrastructure.repository import (
        LOAD_GAP_CLASSIFICATIONS_SQL,
        LOAD_SUCCESSIONS_SQL,
    )

    assert "status = 'approved'" in LOAD_SUCCESSIONS_SQL
    assert "known_from <= :as_of" in LOAD_SUCCESSIONS_SQL
    assert "approved_at <= :as_of" in LOAD_SUCCESSIONS_SQL
    assert "status = 'approved'" in LOAD_GAP_CLASSIFICATIONS_SQL
    assert "known_from <= :as_of" in LOAD_GAP_CLASSIFICATIONS_SQL
    assert "approved_at <= :as_of" in LOAD_GAP_CLASSIFICATIONS_SQL


def test_identity_sql_repository_publish_contract_is_transactional_shape() -> None:
    from src.identity.infrastructure.repository import (
        INSERT_AUDIT_SQL,
        INSERT_RECALC_QUEUE_SQL,
        PUBLISH_DELETE_SQL,
        PUBLISH_INSERT_SQL,
    )

    assert PUBLISH_DELETE_SQL == (
        "DELETE FROM core.series_gap_ranges",
        "DELETE FROM core.series_segments",
        "DELETE FROM core.series_alias",
        "DELETE FROM core.series_members",
        "DELETE FROM core.series_registry",
    )
    for table_name in (
        "core.series_registry",
        "core.series_members",
        "core.series_alias",
        "core.series_gap_ranges",
    ):
        assert table_name in "\n".join(PUBLISH_INSERT_SQL)
    assert "ops.series_identity_build_audit" in INSERT_AUDIT_SQL
    assert "ON CONFLICT (run_id) DO UPDATE" in INSERT_AUDIT_SQL
    assert "ops.indicator_recalc_queue" in INSERT_RECALC_QUEUE_SQL
    assert "ON CONFLICT (symbol, timeframe, range_start_ts, range_end_ts) DO NOTHING" in (
        INSERT_RECALC_QUEUE_SQL
    )
