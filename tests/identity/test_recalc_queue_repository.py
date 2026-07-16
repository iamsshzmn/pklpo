from __future__ import annotations


def test_enqueue_precise_recalc_sql_contract() -> None:
    from src.identity.infrastructure.recalc_queue_repository import (
        ENQUEUE_PRECISE_RECALC_SQL,
    )

    assert "INSERT INTO ops.indicator_recalc_queue" in ENQUEUE_PRECISE_RECALC_SQL
    assert (
        "symbol, timeframe, range_start_ts, range_end_ts, source_dag, detail"
        in ENQUEUE_PRECISE_RECALC_SQL
    )
    assert ":series_id" in ENQUEUE_PRECISE_RECALC_SQL
    assert ":timeframe" in ENQUEUE_PRECISE_RECALC_SQL
    assert ":range_start_ts" in ENQUEUE_PRECISE_RECALC_SQL
    assert ":range_end_ts" in ENQUEUE_PRECISE_RECALC_SQL
    # Precise, per-series/timeframe/range dedupe — distinct from the identity
    # build job's blanket 0..MAX_BIGINT recalc (INSERT_RECALC_QUEUE_SQL), which
    # dedupes on the same unique constraint but always with a full-range row.
    assert (
        "ON CONFLICT (symbol, timeframe, range_start_ts, range_end_ts) DO NOTHING"
        in ENQUEUE_PRECISE_RECALC_SQL
    )
