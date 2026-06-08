"""Smoke tests for the public candles bootstrap boundary."""


def test_import_candles_airflow_callbacks_factory() -> None:
    from src.candles.bootstrap import create_candles_airflow_callbacks

    assert callable(create_candles_airflow_callbacks)
