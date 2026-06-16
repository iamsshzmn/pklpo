"""Contract test: previously-uncovered DAGs bind structured log context.

T3.1 (observability-reliability-track): the five DAGs below must wrap their
task callables in ``airflow_log_context`` from the platform observability
facade so that emitted ``pklpo`` logs carry ``run_id``/``component``/``task_id``.

This test reads DAG *source* (it does not import the modules) so it stays
runnable without the full Airflow/ccxt runtime dependency set.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_DAGS_DIR = Path(__file__).resolve().parents[2] / "ops" / "airflow" / "dags"

# dag filename -> component label expected in airflow_log_context(...)
_NEWLY_COVERED_DAGS = {
    "features_calc.py": "features_calc",
    "feature_eligibility_refresh.py": "feature_eligibility_refresh",
    "indicators_recalc.py": "indicators_recalc",
    "indicators_partition_maintenance.py": "indicators_partition_maintenance",
    "swap_ohlcv_retention.py": "swap_ohlcv_retention",
}

_FACADE_IMPORT = "from src.pklpo_platform.observability import"


@pytest.mark.parametrize(
    ("dag_file", "component"),
    sorted(_NEWLY_COVERED_DAGS.items()),
)
def test_dag_wraps_tasks_in_facade_log_context(dag_file: str, component: str) -> None:
    source = (_DAGS_DIR / dag_file).read_text(encoding="utf-8")

    assert _FACADE_IMPORT in source, (
        f"{dag_file} must import observability via the platform facade"
    )
    assert "airflow_log_context" in source, (
        f"{dag_file} must import airflow_log_context"
    )
    assert "airflow_log_context(" in source, (
        f"{dag_file} must call airflow_log_context to bind log context"
    )
    assert f'component="{component}"' in source, (
        f"{dag_file} must bind component={component!r}"
    )


@pytest.mark.parametrize(
    ("dag_file", "component"),
    sorted(_NEWLY_COVERED_DAGS.items()),
)
def test_dag_does_not_import_infra_logging_at_parse(
    dag_file: str, component: str
) -> None:
    """The facade route must not pull infrastructure logging into the DAG."""
    source = (_DAGS_DIR / dag_file).read_text(encoding="utf-8")

    assert "infrastructure.logging_config" not in source, (
        f"{dag_file} must not import infrastructure.logging_config"
    )
