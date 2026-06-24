from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROMTAIL_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "ops"
    / "monitoring"
    / "promtail"
    / "promtail-config.yml"
)


def _scrape_configs() -> list[dict[str, Any]]:
    return yaml.safe_load(PROMTAIL_CONFIG.read_text(encoding="utf-8"))["scrape_configs"]


def test_promtail_scrapes_only_debug_log_files() -> None:
    paths: list[str] = []
    for config in _scrape_configs():
        for static_config in config["static_configs"]:
            paths.append(static_config["labels"]["__path__"])

    assert "/var/log/pklpo/pklpo_debug.log*" in paths
    assert "/var/log/airflow/pklpo/pklpo_debug.log*" in paths
    assert all("pklpo_errors.log" not in path for path in paths)
    assert all("*.log" not in path for path in paths)
