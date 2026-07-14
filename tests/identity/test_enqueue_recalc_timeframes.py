"""Regression: identity build must not enqueue blanket '*' recalc rows.

ops/airflow/dags/indicators_recalc.py passes `timeframe` verbatim into the
feature pipeline, so a '*' row would be claimed and end up 'blocked' forever.
"""

from src.identity.infrastructure.repository import (
    FULL_RECALC_TIMEFRAMES,
    INSERT_RECALC_QUEUE_SQL,
)


def test_recalc_enqueue_uses_parameterized_timeframe() -> None:
    assert "'*'" not in INSERT_RECALC_QUEUE_SQL
    assert ":timeframe" in INSERT_RECALC_QUEUE_SQL


def test_full_recalc_timeframes_are_full_role_db_notation() -> None:
    assert FULL_RECALC_TIMEFRAMES == ("1H", "4H", "1D")
