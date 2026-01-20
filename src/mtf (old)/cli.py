from __future__ import annotations

import argparse
import asyncio
import logging
import time

from sqlalchemy import text

from src.database import get_async_session
from src.metrics import MetricType, metrics_collector

from .aggregator import aggregate_context, determine_bias_and_consensus
from .combinations import compute_combination_votes
from .features import (
    SUPPORTED_TFS_CONTEXT,
    SUPPORTED_TFS_TRIGGER,
    compute_trend_score,
    detect_data_lag,
    fetch_latest_indicators,
)
from .trigger import evaluate_trigger_probabilities
from .writer import save_mtf_result

logger = logging.getLogger(__name__)

# Доп. файл логов для сигналов
signals_logger = logging.getLogger("signals_mtf")
if not signals_logger.handlers:
    sh = logging.FileHandler("signals.log", encoding="utf-8")
    sh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    signals_logger.addHandler(sh)
    signals_logger.setLevel(logging.INFO)


async def compute_mtf_signal(symbol: str) -> int:
    start_ts = time.perf_counter()
    # 1) Load indicators
    tf_all = list(set(SUPPORTED_TFS_CONTEXT + SUPPORTED_TFS_TRIGGER))
    tf_points = await fetch_latest_indicators(symbol, tf_all)

    # 2) Scores for 1D and 4H
    score_1d = None
    score_4h = None
    if "1Dutc" in tf_points:
        score_1d, _ = compute_trend_score(tf_points["1Dutc"])
    if "4H" in tf_points:
        score_4h, _ = compute_trend_score(tf_points["4H"])

    ctx = aggregate_context(score_1d, score_4h)

    # 3) Trigger probabilities (15m/5m)
    features_15m = _extract_trigger_features(tf_points.get("15m"))
    features_5m = _extract_trigger_features(tf_points.get("5m"))
    p_up, p_down = evaluate_trigger_probabilities(features_15m, features_5m)

    # 4) Combination votes
    votes = await compute_combination_votes(symbol)

    # 5) Decision
    consensus = determine_bias_and_consensus(ctx.bias, p_up, p_down, threshold=0.6)

    # 6) Save
    input_data = {
        "context_score": ctx.context_score,
        "bias": ctx.bias,
        "p_reversal_up": p_up,
        "p_reversal_down": p_down,
        "combination_votes": votes,
    }
    await save_mtf_result(symbol, consensus, input_data, timeframe="15m")
    logger.info(
        f"MTF: symbol={symbol} bias={ctx.bias} p_up={p_up:.2f} p_down={p_down:.2f} out={consensus}"
    )
    # Плоская запись в signals.log
    signals_logger.info(
        f"symbol={symbol} bias={ctx.bias} p_up={p_up:.2f} p_down={p_down:.2f} out={consensus}"
    )
    # Metrics
    elapsed = time.perf_counter() - start_ts
    try:
        await metrics_collector.register_metric(
            "mtf.latency", MetricType.HISTOGRAM, "MTF latency seconds"
        )
        await metrics_collector.observe_histogram(
            "mtf.latency", elapsed, labels={"symbol": symbol}
        )
        # Data lag warning (use 15m expected interval if available)
        latest_15m_ts = tf_points.get("15m").ts if tf_points.get("15m") else None
        now_utc = int(time.time())
        if detect_data_lag(latest_15m_ts, now_utc, expected_seconds=15 * 60):
            logger.warning(
                f"MTF data_lag: symbol={symbol} latest_15m_ts={latest_15m_ts}"
            )
            await metrics_collector.register_metric(
                "mtf.data_lag", MetricType.COUNTER, "MTF data lag events"
            )
            await metrics_collector.increment_counter(
                "mtf.data_lag", 1, labels={"symbol": symbol}
            )
    except Exception:
        pass
    return consensus


def _extract_trigger_features(point) -> dict:
    if not point:
        return {}
    return {
        "ema_fast": point.ema_fast,
        "ema_slow": point.ema_slow,
        "adx": point.adx,
        "vol_std_n": point.vol_std_n,
    }


async def run_for_all_symbols():
    async for session in get_async_session():
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT DISTINCT symbol FROM indicators WHERE timeframe = '15m'"
                    )
                )
            )
            .scalars()
            .all()
        )
        for s in rows:
            try:
                await compute_mtf_signal(s)
            except Exception as e:
                logger.exception(f"MTF compute failed for {s}: {e}")
        break


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("MTF analysis")
    p.add_argument("--symbol", type=str, default=None, help="Ограничить одним символом")
    p.add_argument("--all", action="store_true", help="Запустить для всех символов")
    return p


async def main_async(args: argparse.Namespace):
    if args.symbol:
        await compute_mtf_signal(args.symbol)
    else:
        await run_for_all_symbols()


def main():
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
