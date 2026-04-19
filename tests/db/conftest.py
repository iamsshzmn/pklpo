"""Pytest configuration for tests/db — adds Airflow DAGs directory to sys.path."""
from __future__ import annotations

import sys
from pathlib import Path

_DAGS_DIR = Path(__file__).parent.parent.parent / "ops" / "airflow" / "dags"
if str(_DAGS_DIR) not in sys.path:
    sys.path.insert(0, str(_DAGS_DIR))
