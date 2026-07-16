"""Regression: identity build must not enqueue blanket '*' recalc rows.

ops/airflow/dags/indicators_recalc.py passes `timeframe` verbatim into the
feature pipeline, so a '*' row would be claimed and end up 'blocked' forever.
"""

from src.identity.infrastructure.repository import (
    FEATURE_RECALC_TIMEFRAMES,
    INSERT_RECALC_QUEUE_SQL,
)


def test_recalc_enqueue_uses_parameterized_timeframe() -> None:
    assert "'*'" not in INSERT_RECALC_QUEUE_SQL
    assert ":timeframe" in INSERT_RECALC_QUEUE_SQL


def test_feature_recalc_timeframes_cover_feature_computable_roles() -> None:
    # FULL (1H/4H/1D) + CONTEXT (1W); INFORMATIONAL 1M excluded — no computation.
    assert FEATURE_RECALC_TIMEFRAMES == ("1H", "4H", "1D", "1W")
