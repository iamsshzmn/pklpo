from __future__ import annotations


def test_continuous_sql_repository_publish_contract_is_atomic_shape() -> None:
    from src.identity.infrastructure.continuous_repository import (
        INSERT_CONTINUOUS_AUDIT_SQL,
        INSERT_CONTINUOUS_FAILURE_AUDIT_SQL,
        INSERT_CONTINUOUS_ROWS_SQL,
        INSERT_SEGMENTS_SQL,
        LOAD_RAW_BARS_SQL,
        PUBLISH_DELETE_SQL,
    )

    assert "FROM public.swap_ohlcv_p" in LOAD_RAW_BARS_SQL
    assert "symbol = :source_symbol" in LOAD_RAW_BARS_SQL
    assert "timestamp >= CAST(:load_start AS bigint)" in LOAD_RAW_BARS_SQL
    assert (
        "(CAST(:valid_to AS bigint) IS NULL OR timestamp < CAST(:valid_to AS bigint))"
        in LOAD_RAW_BARS_SQL
    )
    assert "DELETE FROM core.continuous_ohlcv_p" in PUBLISH_DELETE_SQL[0]
    assert "DELETE FROM core.series_segments" in PUBLISH_DELETE_SQL[1]
    assert "INSERT INTO core.continuous_ohlcv_p" in INSERT_CONTINUOUS_ROWS_SQL
    assert "ON CONFLICT (series_id, timeframe, timestamp) DO UPDATE" in (
        INSERT_CONTINUOUS_ROWS_SQL
    )
    assert "INSERT INTO core.series_segments" in INSERT_SEGMENTS_SQL
    assert "ON CONFLICT (series_id, timeframe, segment_id, known_from) DO UPDATE" in (
        INSERT_SEGMENTS_SQL
    )
    assert "ops.continuous_ohlcv_build_audit" in INSERT_CONTINUOUS_AUDIT_SQL
    assert "ON CONFLICT (run_id) DO UPDATE" in INSERT_CONTINUOUS_AUDIT_SQL
    assert "'success'" in INSERT_CONTINUOUS_AUDIT_SQL

    # §17.4: the audit table's status CHECK already allows 'failed'
    # (migration 530), but nothing wrote a failure row before this task.
    assert "ops.continuous_ohlcv_build_audit" in INSERT_CONTINUOUS_FAILURE_AUDIT_SQL
    assert "'failed'" in INSERT_CONTINUOUS_FAILURE_AUDIT_SQL
    assert ":error_type" in INSERT_CONTINUOUS_FAILURE_AUDIT_SQL
    assert ":error_message_hash" in INSERT_CONTINUOUS_FAILURE_AUDIT_SQL
    assert "ON CONFLICT (run_id) DO UPDATE" in INSERT_CONTINUOUS_FAILURE_AUDIT_SQL
