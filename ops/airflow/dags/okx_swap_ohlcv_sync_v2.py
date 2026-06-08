"""
DAG: okx_swap_ohlcv_sync_v2

Purpose
- Collect and load OHLCV candles for OKX SWAP instruments into `swap_ohlcv_p`.
- Optionally (extra_data=True) fetches `funding_rate` and `open_interest`.

Tasks
- refresh_okx_meta: conditionally refreshes instrument metadata (cache < 24h -> skip).
- swap_sync: calls candles interface entrypoint, returns aggregated stats via XCom.
- smoke_validate: quick check for records and fill rate for today.
- quality_pipeline: data-quality checks with alerts.

Run parameters (via dag_run.conf)
- mode: "fast" (default), "slow", "ext", "bootstrap"
- extra_data: bool (default: False)
- timeframes: list[str] (optional, overrides mode)
- symbols: list[str] (optional)
- refresh_instruments: bool (default: False)
- max_concurrent_symbols: int (optional)

Schedule
- schedule="*/5 * * * *": fast every 5 min, slow at 0/15/30/45 (auto-slots).
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.candles.interfaces import (
    AirflowSyncRequest,
    run_refresh_okx_meta,
    run_smoke_validate,
    run_swap_sync,
)


def _get_loop() -> asyncio.AbstractEventLoop:
    """Return a running event loop, creating one if the current loop is closed."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _normalize_async_database_uri(uri: str) -> str:
    """Convert a Postgres URI to the asyncpg variant expected by candles."""
    if uri.startswith("postgresql+asyncpg://"):
        return uri
    if uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+asyncpg://", 1)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+asyncpg://", 1)
    return uri


def _project_env_default(name: str, fallback: str) -> str:
    raw = os.environ.get(name)
    if raw not in {None, ""}:
        return raw

    candidates = [
        Path("/opt/airflow/project/.env"),
        Path(__file__).resolve().parents[3] / ".env",
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


def get_dag_env() -> dict[str, str]:
    """Pull secrets from Airflow Connection 'pklpo_db' and non-secret vars from Variables."""
    from airflow.hooks.base import BaseHook
    from airflow.models import Variable

    env: dict[str, str] = {}

    try:
        conn = BaseHook.get_connection("pklpo_db")
        if not conn:
            raise RuntimeError("Airflow connection 'pklpo_db' is not configured")
        env["DATABASE_URL"] = _normalize_async_database_uri(conn.get_uri())
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
        default_var=_project_env_default("OBSERVABILITY_PROMETHEUS_ENABLED", "false"),
    )
    env["OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL"] = Variable.get(
        "observability_prometheus_pushgateway_url",
        default_var=_project_env_default(
            "OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091"
        ),
    )
    env["OBSERVABILITY_JOB_NAME"] = Variable.get(
        "observability_job_name",
        default_var=_project_env_default("OBSERVABILITY_JOB_NAME", "data_quality_pipeline"),
    )
    env["OBSERVABILITY_METRICS_PREFIX"] = Variable.get(
        "observability_metrics_prefix",
        default_var=_project_env_default("OBSERVABILITY_METRICS_PREFIX", "pklpo"),
    )
    return env


def setup_env(env: dict[str, str]) -> None:
    """Set env vars and ensure required directories exist."""
    import os

    for key, value in env.items():
        os.environ[key] = value

    directories = {
        Path(env["MARKET_META_LOG_FILE"]).parent,
        Path(env["MARKET_META_DATA_DIR"]),
        Path(env["INSTRUMENTS_CACHE_DIR"]),
    }
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def _normalize_run_type(run_type: Any) -> str | None:
    if run_type is None:
        return None
    value = getattr(run_type, "value", run_type)
    return str(value)


def _build_request(context) -> AirflowSyncRequest:
    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}
    return AirflowSyncRequest(
        conf=conf,
        logical_date=context.get("logical_date"),
        run_type=_normalize_run_type(getattr(dag_run, "run_type", None)),
    )


def refresh_okx_meta_task(**context):
    """Refresh the instruments catalogue using the candles interface entrypoint."""
    env = get_dag_env()
    setup_env(env)

    result = _get_loop().run_until_complete(run_refresh_okx_meta(_build_request(context)))
    if result["refreshed"]:
        print("[refresh_okx_meta] load_instruments finished OK")
    else:
        print("[refresh_okx_meta] Cache is fresh -> skipping instruments refresh")
    return result


def swap_sync_task(**context):
    """Run swap sync via the candles interface entrypoint."""
    env = get_dag_env()
    setup_env(env)

    request = _build_request(context)
    if request.is_manual:
        print("[swap_sync] Manual run -> bypassing freshness gate")

    result = _get_loop().run_until_complete(run_swap_sync(request))
    if result.get("skipped"):
        print(f"[swap_sync] Skipped -> {result['reason']}")
    else:
        print(f"[swap_sync] Completed: {result}")
    return result


def smoke_validate_task(**context):
    """Run smoke validation via the candles interface entrypoint."""
    env = get_dag_env()
    setup_env(env)

    result = _get_loop().run_until_complete(run_smoke_validate(_build_request(context)))

    print(f"[smoke_validate] total_rows={result['total_rows']:,}")
    if result["lag_sec"] is not None:
        print(f"[smoke_validate] max_ts lag={result['lag_sec']:.0f}s")
    print(
        f"[smoke_validate] today rows={result['rows_today']} "
        f"FR={result['fr_filled']} OI={result['oi_filled']}"
    )
    for tf, lag in result.get("tf_lags", {}).items():
        print(f"[smoke_validate] lag {tf}: {lag:.0f}s")
    if result["fr_pct"] is not None:
        print(
            f"[smoke_validate] FR fill={result['fr_pct']:.1f}% "
            f"OI fill={result['oi_pct']:.1f}%"
        )
        if result["fr_pct"] < 50:
            print(f"WARNING: Low funding_rate fill rate: {result['fr_pct']:.1f}%")
        if result["oi_pct"] is not None and result["oi_pct"] < 50:
            print(f"WARNING: Low open_interest fill rate: {result['oi_pct']:.1f}%")

    print("[smoke_validate] finished OK")
    return result


def validate_swap_sync_xcom_task(**context):
    """Read and validate swap_sync XCom payload."""
    ti = context["ti"]
    payload = ti.xcom_pull(task_ids="swap_sync", key="return_value")
    if not isinstance(payload, dict):
        raise ValueError(f"swap_sync XCom must be dict, got {type(payload).__name__}")

    required_keys = ("mode",)
    missing_keys = [key for key in required_keys if key not in payload]
    if missing_keys:
        raise ValueError(f"swap_sync XCom missing required keys: {missing_keys}")

    skipped = bool(payload.get("skipped", False))

    if skipped:
        print(
            f"[validate_swap_sync_xcom] skipped mode={payload.get('mode')} "
            f"reason={payload.get('reason', 'unknown')}"
        )
        return payload

    sync_required_keys = (
        "mode",
        "timeframes",
        "symbols_count",
        "total_symbols_processed",
        "duration_sec",
        "rows_upserted_total",
        "errors_count",
        "candles_per_second",
        "api_429_count",
        "api_timeout_count",
        "today_fill",
    )
    missing_sync_keys = [key for key in sync_required_keys if key not in payload]
    if missing_sync_keys:
        raise ValueError(f"swap_sync XCom missing sync keys: {missing_sync_keys}")
    if payload["rows_upserted_total"] == 0:
        raise ValueError("swap_sync total failure: rows_upserted_total == 0")
    if payload["total_symbols_processed"] == 0:
        raise ValueError("swap_sync total failure: total_symbols_processed == 0")

    print(
        "[validate_swap_sync_xcom] "
        f"mode={payload['mode']} "
        f"timeframes={payload['timeframes']} "
        f"symbols_count={payload['symbols_count']} "
        f"total_symbols_processed={payload['total_symbols_processed']} "
        f"rows_upserted_total={payload['rows_upserted_total']} "
        f"api_429_count={payload['api_429_count']}"
    )
    return payload


def quality_pipeline_task(**context):
    """Run data quality checks and dispatch alerts."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from src.candles.application.quality_pipeline import run_quality_pipeline
    from src.candles.infrastructure.sqlalchemy_pool_adapter import (
        SQLAlchemyPoolAdapter,
    )

    env = get_dag_env()
    setup_env(env)

    loop = _get_loop()

    async def _run():
        engine = create_async_engine(env["DATABASE_URL"])
        pool = SQLAlchemyPoolAdapter(engine)
        try:
            report, alert_stats = await run_quality_pipeline(pool, send_alerts=True)
            violations = sum(1 for r in report.results if str(r.severity) != "ok")
            print(
                f"[quality_pipeline] total_checks={len(report.results)} "
                f"violations={violations} alert_stats={alert_stats}"
            )
            return {
                "total_checks": len(report.results),
                "violations": violations,
                "alert_stats": alert_stats,
            }
        finally:
            await engine.dispose()

    return loop.run_until_complete(_run())


default_args = {
    "owner": "okx_swap_ohlcv_sync",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="okx_swap_ohlcv_sync_v2",
    start_date=datetime(2025, 1, 1),
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
) as dag:
    refresh_okx = PythonOperator(
        task_id="refresh_okx_meta",
        python_callable=refresh_okx_meta_task,
        pool="okx_api_pool",
        pool_slots=1,
    )

    swap_sync = PythonOperator(
        task_id="swap_sync",
        python_callable=swap_sync_task,
        pool="ohlcv_write_pool",
        pool_slots=1,
    )

    validate_swap_sync_xcom = PythonOperator(
        task_id="validate_swap_sync_xcom",
        python_callable=validate_swap_sync_xcom_task,
    )

    smoke_validate = PythonOperator(
        task_id="smoke_validate",
        python_callable=smoke_validate_task,
    )

    quality_pipeline = PythonOperator(
        task_id="quality_pipeline",
        python_callable=quality_pipeline_task,
        trigger_rule="all_done",
    )

    refresh_okx >> swap_sync >> validate_swap_sync_xcom >> smoke_validate >> quality_pipeline
