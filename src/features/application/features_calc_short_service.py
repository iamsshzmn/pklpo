from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.features.application.feature_window import (
    check_has_new_ohlcv,
    get_last_calculated_ts,
    get_ohlcv_window,
    timeout_for_timeframe,
)
from src.features.application.freshness_gate import (
    FreshnessGateConfig,
    check_has_work_to_do,
)
from src.features.core import compute_features
from src.features.infrastructure.persistence.inserter import insert_indicators
from src.market_meta.application.quality_pipeline import run_quality_pipeline
from src.market_meta.infrastructure.sqlalchemy_pool_adapter import SQLAlchemyPoolAdapter
from src.features.presets.features_calc_short_v1 import FEATURES_CALC_SHORT_SPECS
from src.logging import get_logger

logger = get_logger("features.application.features_calc_short_service")


def get_or_create_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


async def save_features_batch(
    session: AsyncSession,
    df_features: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> int:
    payload = df_features.copy()
    payload["symbol"] = symbol
    payload["timeframe"] = timeframe

    if "timestamp" not in payload.columns:
        if "ts" in payload.columns:
            payload["timestamp"] = payload["ts"] * 1000
        else:
            raise ValueError("DataFrame must have 'timestamp' or 'ts' column")

    return await insert_indicators(
        session=session,
        ind_df=payload,
        symbol=symbol,
        timeframe=timeframe,
    )


async def process_symbol_features(
    session: AsyncSession,
    symbol: str,
    timeframes: list[str],
    specs: list[str],
    *,
    warmup_bars: int = 500,
) -> dict[str, Any]:
    symbol_start = time.time()
    results: dict[str, Any] = {}
    errors: list[str] = []

    for timeframe in timeframes:
        tf_start = time.time()
        timeout = timeout_for_timeframe(timeframe)
        try:
            last_feature_ts = await get_last_calculated_ts(session, symbol, timeframe)
            has_new, _latest_ohlcv_ts = await check_has_new_ohlcv(
                session, symbol, timeframe, last_feature_ts
            )
            if not has_new:
                results[timeframe] = {
                    "status": "skipped",
                    "reason": "no_new_ohlcv",
                    "compute_time_seconds": round(time.time() - tf_start, 2),
                }
                continue

            df_ohlcv = await get_ohlcv_window(
                session,
                symbol,
                timeframe,
                last_feature_ts,
                warmup_bars=warmup_bars,
            )
            if len(df_ohlcv) == 0:
                results[timeframe] = {
                    "status": "skipped",
                    "reason": "no_data",
                    "compute_time_seconds": round(time.time() - tf_start, 2),
                }
                continue

            df_features = await asyncio.wait_for(
                asyncio.to_thread(
                    compute_features,
                    df_ohlcv,
                    specs=specs,
                    volatility_normalize=False,
                    debug=False,
                ),
                timeout=timeout,
            )

            rows_saved = await save_features_batch(session, df_features, symbol, timeframe)
            results[timeframe] = {
                "rows_processed": len(df_ohlcv),
                "rows_saved": rows_saved,
                "status": "ok",
                "bars_loaded": len(df_ohlcv),
                "compute_time_seconds": round(time.time() - tf_start, 2),
            }
        except TimeoutError:
            error_msg = f"{symbol}/{timeframe}: timeout ({timeout}s)"
            errors.append(error_msg)
            logger.warning(error_msg)
            results[timeframe] = {
                "status": "error",
                "error": "timeout",
                "compute_time_seconds": round(time.time() - tf_start, 2),
            }
        except Exception as exc:  # pragma: no cover - defensive branch
            error_msg = f"{symbol}/{timeframe}: {exc!s}"
            errors.append(error_msg)
            logger.exception("Failed symbol/timeframe processing: %s", error_msg)
            results[timeframe] = {
                "status": "error",
                "error": str(exc),
                "compute_time_seconds": round(time.time() - tf_start, 2),
            }

    has_saved_data = any(
        isinstance(r, dict)
        and isinstance(r.get("rows_saved"), int)
        and r.get("rows_saved", 0) > 0
        for r in results.values()
    )
    if has_saved_data and not errors:
        await session.commit()
    elif errors:
        await session.rollback()

    return {
        "symbol": symbol,
        "results": results,
        "errors": errors,
        "success": len(errors) == 0,
        "total_duration_seconds": round(time.time() - symbol_start, 2),
        "timeframes_processed": len(
            [
                r
                for r in results.values()
                if isinstance(r, dict) and r.get("status") == "ok"
            ]
        ),
        "timeframes_failed": len(
            [
                r
                for r in results.values()
                if isinstance(r, dict) and r.get("status") == "error"
            ]
        ),
    }


async def process_all_symbols(
    engine: AsyncEngine,
    symbols: list[str] | None,
    timeframes: list[str],
    specs: list[str],
    *,
    max_concurrent_symbols: int = 3,
    warmup_bars: int = 500,
) -> dict[str, Any]:
    async with AsyncSession(engine) as temp_session:
        if not symbols:
            res = await temp_session.execute(
                text("SELECT DISTINCT symbol FROM swap_ohlcv_p ORDER BY symbol")
            )
            symbols = [row[0] for row in res.fetchall()]

    semaphore = asyncio.Semaphore(max_concurrent_symbols)

    async def process_with_semaphore(symbol: str):
        async with semaphore:
            async with AsyncSession(engine) as symbol_session:
                return await process_symbol_features(
                    symbol_session,
                    symbol,
                    timeframes,
                    specs,
                    warmup_bars=warmup_bars,
                )

    tasks = [process_with_semaphore(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_symbols = len(symbols)
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))

    return {
        "total_symbols": total_symbols,
        "successful": successful,
        "failed": total_symbols - successful,
        "results": results,
    }


async def run_features_calc_short(
    *,
    database_url: str,
    symbols: list[str] | None,
    timeframes: list[str],
    max_concurrent_symbols: int,
    is_manual_run: bool,
    max_lag_fast: int = 240,
    max_lag_slow: int = 1200,
    warmup_bars: int = 500,
) -> dict[str, Any]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        if not is_manual_run:
            async with AsyncSession(engine) as session:
                has_work = await check_has_work_to_do(
                    session,
                    timeframes,
                    is_manual_run=is_manual_run,
                    config=FreshnessGateConfig(
                        max_lag_fast=max_lag_fast,
                        max_lag_slow=max_lag_slow,
                    ),
                )
                if not has_work:
                    return {
                        "skipped": True,
                        "reason": "ohlcv_fresh_and_synced",
                        "message": (
                            "All timeframes are fresh and synchronized, calculation is not required"
                        ),
                    }

        stats = await process_all_symbols(
            engine=engine,
            symbols=symbols,
            timeframes=timeframes,
            specs=FEATURES_CALC_SHORT_SPECS,
            max_concurrent_symbols=max_concurrent_symbols,
            warmup_bars=warmup_bars,
        )
        rows_saved_total = sum(
            r.get("results", {}).get(tf, {}).get("rows_saved", 0)
            for r in stats["results"]
            if isinstance(r, dict)
            for tf in timeframes
        )
        total_compute_time = sum(
            r.get("total_duration_seconds", 0)
            for r in stats["results"]
            if isinstance(r, dict)
        )
        avg_compute_time = (
            total_compute_time / stats["total_symbols"] if stats["total_symbols"] > 0 else 0
        )
        symbols_with_work = sum(
            1
            for r in stats["results"]
            if isinstance(r, dict) and r.get("timeframes_processed", 0) > 0
        )
        return {
            "total_symbols": stats["total_symbols"],
            "successful": stats["successful"],
            "failed": stats["failed"],
            "rows_saved_total": rows_saved_total,
            "symbols_with_work": symbols_with_work,
            "total_compute_time_seconds": round(total_compute_time, 2),
            "avg_compute_time_per_symbol_seconds": round(avg_compute_time, 2),
        }
    finally:
        await engine.dispose()


async def run_features_calc_short_validate(
    *,
    database_url: str,
    quality_enabled: bool,
    quality_send_alerts: bool,
    quality_alert_cooldown: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "lag_seconds": {},
        "quality_postcheck_enabled": quality_enabled,
    }
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with AsyncSession(engine) as session:
            for tf in ["1m", "5m"]:
                max_ts = (
                    await session.execute(
                        text(
                            """
                            SELECT MAX(timestamp)
                            FROM indicators
                            WHERE timeframe = :tf
                            """
                        ),
                        {"tf": tf},
                    )
                ).scalar()
                if max_ts:
                    lag_sec = (datetime.now(UTC).timestamp() * 1000 - max_ts) / 1000
                    result["lag_seconds"][tf] = round(lag_sec, 2)

        if quality_enabled:
            pool_adapter = SQLAlchemyPoolAdapter(engine)
            report, alert_stats = await run_quality_pipeline(
                pool_adapter,
                send_alerts=quality_send_alerts,
                alert_cooldown_minutes=quality_alert_cooldown,
            )
            summary = report.summary()
            result.update(
                {
                    "quality_total_checks": summary.get("total", 0),
                    "quality_warn": summary.get("warn", 0),
                    "quality_critical": summary.get("critical", 0),
                    "quality_ok": summary.get("ok", 0),
                    "alerts_checked": alert_stats.get("checked", 0),
                    "alerts_sent": alert_stats.get("sent", 0),
                    "alerts_suppressed": alert_stats.get("suppressed", 0),
                }
            )
    finally:
        await engine.dispose()
    return result
