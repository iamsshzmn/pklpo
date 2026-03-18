"""Business logic for OKX swap OHLCV sync — extracted from the Airflow DAG."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Mode presets
# ---------------------------------------------------------------------------

MODE_CONFIGS: dict[str, dict[str, Any]] = {
    "fast": {
        "timeframes": ["1m", "5m"],
        "extra_data": False,
        "max_concurrent_symbols": 10,
        "max_requests_per_second": 20,
    },
    "slow": {
        "timeframes": ["15m", "30m", "1H", "4H", "12H", "1D", "1W", "1M"],
        "extra_data": False,
        "max_concurrent_symbols": 2,
        "max_requests_per_second": 15,
    },
    "ext": {
        "timeframes": ["1m", "5m"],
        "extra_data": True,
        "max_concurrent_symbols": 5,
        "max_requests_per_second": 15,
    },
    "bootstrap": {
        "timeframes": None,  # uses SWAP_BARS from sync_swap_candles
        "extra_data": True,
        "max_concurrent_symbols": 1,
        "max_requests_per_second": 15,
    },
}


def resolve_sync_mode(conf: dict[str, Any], execution_date: datetime | None) -> str:
    """Return the effective mode string for a DAG run.

    Scheduled runs with an empty conf auto-slot into "slow" at :00/:15/:30/:45,
    otherwise "fast". Manual runs pass mode explicitly via conf.
    """
    if conf.get("mode"):
        return str(conf["mode"])
    if execution_date is not None:
        return "slow" if execution_date.minute in (0, 15, 30, 45) else "fast"
    return "fast"


def build_sync_config(
    conf: dict[str, Any],
    execution_date: datetime | None,
) -> dict[str, Any]:
    """Build the full sync configuration dict from dag_run.conf and execution context."""
    mode = resolve_sync_mode(conf, execution_date)
    base_config: dict[str, Any] = dict(
        cast("dict[str, Any]", MODE_CONFIGS.get(mode, MODE_CONFIGS["fast"]))
    )

    if "timeframes" in conf:
        base_config["timeframes"] = conf["timeframes"]
    if "extra_data" in conf:
        base_config["extra_data"] = conf["extra_data"]
    if "max_concurrent_symbols" in conf:
        base_config["max_concurrent_symbols"] = conf["max_concurrent_symbols"]
    if "symbols" in conf:
        base_config["symbols"] = conf["symbols"]

    base_config["mode"] = mode
    base_config["batch_size"] = 300
    base_config["max_retries"] = 5
    base_config["retry_delay"] = 1.5

    return base_config


# ---------------------------------------------------------------------------
# Freshness gate
# ---------------------------------------------------------------------------


async def check_data_freshness(
    session: AsyncSession, mode: str
) -> tuple[bool, str]:
    """Check whether swap_ohlcv_p data is fresh enough to skip a sync run.

    Returns:
        (should_skip, reason) — True if the data is fresh and sync can be skipped.
    """
    timeframe_to_check = "1m" if mode == "fast" else "15m"
    max_lag_seconds = 120 if mode == "fast" else 900

    res = await session.execute(
        text(
            "SELECT MAX(timestamp) FROM swap_ohlcv_p WHERE timeframe = :tf"
        ),
        {"tf": timeframe_to_check},
    )
    max_ts_ms = res.scalar()

    if not max_ts_ms:
        return False, f"no_data_for_{timeframe_to_check}"

    max_ts_dt = datetime.fromtimestamp(max_ts_ms / 1000, tz=UTC)
    lag_sec = (datetime.now(UTC) - max_ts_dt).total_seconds()

    if lag_sec < max_lag_seconds:
        return True, (
            f"data_fresh: {timeframe_to_check} lag {lag_sec:.0f}s < {max_lag_seconds}s"
        )

    return False, (
        f"stale: {timeframe_to_check} lag {lag_sec:.0f}s >= {max_lag_seconds}s"
    )


# ---------------------------------------------------------------------------
# Instruments cache check
# ---------------------------------------------------------------------------


def should_refresh_instruments(
    conf: dict[str, Any],
    cache_dir: Path | None = None,
) -> bool:
    """Return True if the instruments list should be refreshed."""
    if conf.get("refresh_instruments", False):
        return True

    effective_dir = cache_dir or Path(
        os.environ.get("INSTRUMENTS_CACHE_DIR", "/tmp/pklpo")  # noqa: S108
    )
    cache_file = effective_dir / "instruments_list.json"
    if cache_file.exists():
        age_hours = (
            datetime.now(UTC).timestamp()
            - datetime.fromtimestamp(cache_file.stat().st_mtime, tz=UTC).timestamp()
        ) / 3600
        if age_hours < 24:
            return False

    return True


# ---------------------------------------------------------------------------
# XCom stats formatter
# ---------------------------------------------------------------------------


def format_stats_for_xcom(
    stats: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Build the compact stats dict written to XCom by swap_sync_task."""
    endpoint_stats = stats.get("endpoint_stats", {})
    api_429_count = 0
    if isinstance(endpoint_stats, dict):
        for endpoint_data in endpoint_stats.values():
            if isinstance(endpoint_data, dict):
                api_429_count += endpoint_data.get("rate_limit", 0)

    return {
        "mode": config.get("mode", "unknown"),
        "timeframes": config.get("timeframes", []),
        "symbols_count": stats.get("total_symbols", 0),
        "duration_sec": round(stats.get("duration_seconds", 0), 2),
        "rows_upserted_total": stats.get("total_candles_synced", 0),
        "errors_count": stats.get("errors_count", 0),
        "candles_per_second": round(stats.get("candles_per_second", 0), 2),
        "api_429_count": api_429_count,
        "api_timeout_count": 0,
        "today_fill": stats.get("today_fill", {}),
    }


# ---------------------------------------------------------------------------
# Smoke validation queries
# ---------------------------------------------------------------------------


async def run_smoke_validation(
    session: AsyncSession,
    mode: str,
    extra_data_enabled: bool,
) -> dict[str, Any]:
    """Run data-presence and fill-rate checks against swap_ohlcv_p.

    Returns a dict with key metrics for logging.
    """
    res_total = await session.execute(text("SELECT COUNT(*) FROM swap_ohlcv_p"))
    total_rows = res_total.scalar() or 0

    res_max = await session.execute(
        text("SELECT MAX(timestamp) FROM swap_ohlcv_p")
    )
    max_ts_ms = res_max.scalar()
    lag_sec: float | None = None
    if max_ts_ms:
        lag_sec = (datetime.now(UTC).timestamp() * 1000 - max_ts_ms) / 1000

    start_of_day_ms = int(
        datetime.now(UTC)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
        * 1000
    )
    res_today = await session.execute(
        text(
            """
            SELECT
                COUNT(*) AS rows_today,
                COUNT(*) FILTER (WHERE funding_rate IS NOT NULL) AS fr_filled,
                COUNT(*) FILTER (WHERE open_interest IS NOT NULL) AS oi_filled
            FROM swap_ohlcv_p
            WHERE timestamp >= :start_ms
            """
        ),
        {"start_ms": start_of_day_ms},
    )
    rows_today, fr_filled, oi_filled = res_today.fetchone()

    tf_lags: dict[str, float] = {}
    if mode in ("fast", "ext"):
        for tf in ["1m", "5m"]:
            res_tf = await session.execute(
                text(
                    "SELECT MAX(timestamp) FROM swap_ohlcv_p WHERE timeframe = :tf"
                ),
                {"tf": tf},
            )
            max_tf_ts = res_tf.scalar()
            if max_tf_ts:
                tf_lags[tf] = (
                    datetime.now(UTC).timestamp() * 1000 - max_tf_ts
                ) / 1000

    fr_pct: float | None = None
    oi_pct: float | None = None
    if extra_data_enabled and rows_today:
        fr_pct = (fr_filled / rows_today) * 100
        oi_pct = (oi_filled / rows_today) * 100

    return {
        "total_rows": total_rows,
        "lag_sec": lag_sec,
        "rows_today": rows_today,
        "fr_filled": fr_filled,
        "oi_filled": oi_filled,
        "tf_lags": tf_lags,
        "fr_pct": fr_pct,
        "oi_pct": oi_pct,
    }
