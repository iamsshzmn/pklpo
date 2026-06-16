from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "dag_path",
    [
        Path("ops/airflow/dags/okx_swap_ohlcv_sync_v2.py"),
        Path("ops/airflow/dags/okx_swap_repair_v1.py"),
        Path("ops/airflow/dags/features_calc_short.py"),
        Path("ops/airflow/dags/market_selection.py"),
        Path("ops/airflow/dags/pipeline_monitoring.py"),
    ],
)
def test_key_airflow_dags_use_structured_log_context(dag_path: Path) -> None:
    source = dag_path.read_text(encoding="utf-8")

    assert "airflow_log_context" in source
    assert "with airflow_log_context(" in source
