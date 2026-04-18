"""Shared Airflow environment/bootstrap helpers for repair DAGs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


def normalize_async_database_uri(uri: str) -> str:
    """Convert supported PostgreSQL URIs to the asyncpg variant."""
    if uri.startswith("postgresql+asyncpg://"):
        return uri
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+asyncpg://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+asyncpg://", 1)
    return uri


def project_env_default(name: str, fallback: str) -> str:
    """Read a fallback value from process env or project-level .env files."""
    raw = os.environ.get(name)
    if raw not in {None, ""}:
        return raw

    candidates = [
        Path("/opt/airflow/project/.env"),
        Path(__file__).resolve().parents[4] / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == name:
                return value.strip().strip("'\"")
    return fallback


def get_dag_env(*, job_name_default: str) -> dict[str, str]:
    """Pull secrets from Airflow Connection/Variables for repair DAG runtime."""
    from airflow.hooks.base import BaseHook
    from airflow.models import Variable

    env: dict[str, str] = {}
    try:
        conn = BaseHook.get_connection("pklpo_db")
        if not conn:
            raise RuntimeError("Airflow connection 'pklpo_db' is not configured")
        env["DATABASE_URL"] = normalize_async_database_uri(conn.get_uri())
    except Exception as exc:
        raise RuntimeError(
            "DATABASE_URL not configured. Set Airflow Connection 'pklpo_db'."
        ) from exc

    env["DATABASE_SSL"] = Variable.get("pklpo_database_ssl", default_var="disable")
    env["MARKET_META_LOG_FILE"] = Variable.get(
        "market_meta_log_file", default_var="/tmp/pklpo/market_meta.log"  # noqa: S108
    )
    env["MARKET_META_FILE_LOG"] = Variable.get("market_meta_file_log", default_var="true")
    env["MARKET_META_LOG_LEVEL"] = Variable.get("market_meta_log_level", default_var="DEBUG")
    env["MARKET_META_DATA_DIR"] = Variable.get(
        "market_meta_data_dir", default_var="/tmp/pklpo/data"  # noqa: S108
    )
    env["INSTRUMENTS_CACHE_DIR"] = Variable.get(
        "instruments_cache_dir", default_var="/tmp/pklpo"  # noqa: S108
    )
    env["OBSERVABILITY_PROMETHEUS_ENABLED"] = Variable.get(
        "observability_prometheus_enabled",
        default_var=project_env_default("OBSERVABILITY_PROMETHEUS_ENABLED", "false"),
    )
    env["OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL"] = Variable.get(
        "observability_prometheus_pushgateway_url",
        default_var=project_env_default(
            "OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091"
        ),
    )
    env["OBSERVABILITY_JOB_NAME"] = Variable.get(
        "observability_job_name",
        default_var=project_env_default("OBSERVABILITY_JOB_NAME", job_name_default),
    )
    env["OBSERVABILITY_METRICS_PREFIX"] = Variable.get(
        "observability_metrics_prefix",
        default_var=project_env_default("OBSERVABILITY_METRICS_PREFIX", "pklpo"),
    )
    return env


def setup_env(env: Mapping[str, str | None]) -> None:
    """Set process env vars and create the directories the DAG runtime expects."""
    for key, value in env.items():
        if value not in {None, ""}:
            os.environ[key] = value

    log_file = env.get("MARKET_META_LOG_FILE")
    data_dir = env.get("MARKET_META_DATA_DIR")
    cache_dir = env.get("INSTRUMENTS_CACHE_DIR")
    directories = {
        Path(log_file).parent if log_file else None,
        Path(data_dir) if data_dir else None,
        Path(cache_dir) if cache_dir else None,
    }
    for directory in directories:
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
