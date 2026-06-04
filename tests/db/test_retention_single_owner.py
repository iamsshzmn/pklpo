from __future__ import annotations

from pathlib import Path


def test_market_selection_cleanup_is_not_generic_retention_owner() -> None:
    source = Path("ops/airflow/dags/market_selection.py").read_text(encoding="utf-8")

    assert 'task_id="cleanup_old_data"' not in source
    assert 'task_id="skip_cleanup_old_data"' not in source
    assert "cleanup_old_market_selection_data" in source
    assert "cleanup_old_swap_data" not in source
    assert "swap_ohlcv_p" not in source


def test_swap_ohlcv_retention_is_the_only_ohlcv_cleanup_dag_entrypoint() -> None:
    source = Path("ops/airflow/dags/swap_ohlcv_retention.py").read_text(
        encoding="utf-8"
    )

    assert "SELECT * FROM cleanup_old_swap_data" in source
    assert 'task_id="cleanup_swap_ohlcv"' in source
