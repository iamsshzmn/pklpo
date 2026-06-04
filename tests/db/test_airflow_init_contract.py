from __future__ import annotations

import tomllib
from pathlib import Path

import yaml


def test_test_extra_includes_hypothesis_for_property_tests() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    test_deps = pyproject["project"]["optional-dependencies"]["test"]

    assert "hypothesis==6.151.6" in test_deps


def test_airflow_init_precreates_required_pools() -> None:
    compose = yaml.safe_load(
        Path("ops/airflow/docker-compose.airflow.yml").read_text(encoding="utf-8")
    )
    entrypoint = "\n".join(
        str(part) for part in compose["services"]["airflow-init"]["entrypoint"]
    )

    assert "airflow pools set ohlcv_write_pool 1" in entrypoint
    assert "airflow pools set okx_api_pool 2" in entrypoint
    assert "airflow pools set compute_pool 2" in entrypoint
