from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def _operator_block(path: str, task_id: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(
        rf"PythonOperator\(\s*task_id=[\"']{re.escape(task_id)}[\"'],(?P<body>.*?)\n\s*\)",
        text,
        flags=re.DOTALL,
    )
    assert match is not None, f"{path} has no PythonOperator task_id={task_id!r}"
    return match.group(0)


def _assert_pool(path: str, task_id: str, pool: str) -> None:
    block = _operator_block(path, task_id)
    assert f'pool="{pool}"' in block
    assert "pool_slots=1" in block


def test_ohlcv_mutating_tasks_use_write_pool() -> None:
    _assert_pool(
        "ops/airflow/dags/okx_swap_ohlcv_sync_v2.py", "swap_sync", "ohlcv_write_pool"
    )
    _assert_pool(
        "ops/airflow/dags/okx_swap_ohlcv_bootstrap_v1.py",
        "bootstrap_symbol_tf",
        "ohlcv_write_pool",
    )
    _assert_pool(
        "ops/airflow/dags/okx_swap_repair_v1.py", "swap_repair", "ohlcv_write_pool"
    )
    _assert_pool(
        "ops/airflow/dags/swap_ohlcv_retention.py",
        "cleanup_swap_ohlcv",
        "ohlcv_write_pool",
    )


def test_compute_tasks_use_compute_pool() -> None:
    _assert_pool(
        "ops/airflow/dags/features_calc_short.py",
        "features_calc_short_run",
        "compute_pool",
    )
    _assert_pool("ops/airflow/dags/features_calc.py", "features_run", "compute_pool")
    _assert_pool(
        "ops/airflow/dags/features_calc.py", "combinations_run", "compute_pool"
    )


def test_api_only_task_uses_okx_api_pool() -> None:
    _assert_pool(
        "ops/airflow/dags/okx_swap_ohlcv_sync_v2.py",
        "refresh_okx_meta",
        "okx_api_pool",
    )


def test_airflow_readme_documents_required_pools() -> None:
    readme = (ROOT / "ops/airflow/README.md").read_text(encoding="utf-8")

    assert (
        'airflow pools set ohlcv_write_pool 1 "Serialize swap_ohlcv_p writers"'
        in readme
    )
    assert 'airflow pools set okx_api_pool 2 "Throttle OKX API calls"' in readme
    assert 'airflow pools set compute_pool 2 "Throttle feature compute tasks"' in readme
