"""Run grouped feature benchmark and save results as JSON artifact.

Usage:
    python scripts/run_features_group_benchmark.py [--rows N] [--runs N] [--out PATH]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import time
from pathlib import Path


def _make_ohlcv(rows: int, seed: int = 0):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    close = 100.0 + rng.normal(0, 0.5, rows).cumsum()
    open_ = close + rng.normal(0, 0.2, rows)
    high = np.maximum(open_, close) + abs(rng.normal(0, 0.3, rows))
    low = np.minimum(open_, close) - abs(rng.normal(0, 0.3, rows))
    volume = rng.integers(1000, 5000, rows).astype(float)

    import pandas as pd

    return pd.DataFrame(
        {
            "ts": (np.arange(rows) + 1_700_000_000),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _benchmark_group(calculator, df, group: str, available: set[str], runs: int) -> dict:
    import tracemalloc

    times: list[float] = []
    for _ in range(runs):
        tracemalloc.start()
        t0 = time.perf_counter()
        calculator.calculate_group(df.copy(), group, available=available)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        times.append(elapsed)

    times_sorted = sorted(times)
    p50 = times_sorted[len(times_sorted) // 2]
    p95_idx = min(int(len(times_sorted) * 0.95), len(times_sorted) - 1)
    p95 = times_sorted[p95_idx]
    return {"p50_seconds": round(p50, 4), "p95_seconds": round(p95, 4)}


GROUP_AVAILABLE = {
    "overlap": {"hl2"},
    "ma": {"ema_21", "sma_20"},
    "oscillators": {"rsi_14"},
    "volatility": {"atr_14"},
    "volume": {"obv"},
    "trend": {"adx_14"},
    "candles": {"ha_close"},
    "squeeze": {"ttm_squeeze_hist"},
    "statistics": {"zscore_20"},
    "performance": {"log_return"},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Features group benchmark")
    parser.add_argument("--rows", type=int, default=int(os.environ.get("FEATURES_BENCH_ROWS", "10000")))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON path (default: benchmarks/results/group_baseline_<date>.json)",
    )
    args = parser.parse_args()

    from src.features.core.group_calculation import CALCULATION_ORDER
    from src.features.core.group_calculator import GroupFeatureCalculator

    calculator = GroupFeatureCalculator()
    df = _make_ohlcv(args.rows)

    print(f"[benchmark] rows={args.rows}, runs={args.runs}")
    group_results: dict[str, dict] = {}
    for group in CALCULATION_ORDER:
        available = GROUP_AVAILABLE.get(group, set())
        print(f"  [{group}] ...", end=" ", flush=True)
        stats = _benchmark_group(calculator, df, group, available, args.runs)
        group_results[group] = stats
        print(f"p50={stats['p50_seconds']:.3f}s  p95={stats['p95_seconds']:.3f}s")

    today = datetime.date.today().strftime("%Y%m%d")
    out_path = args.out or f"benchmarks/results/group_baseline_{today}.json"
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    backend = os.environ.get("FEATURES_TA_BACKEND", "auto")
    result = {
        "timestamp_utc": datetime.datetime.utcnow().isoformat() + "+00:00",
        "backend": backend,
        "benchmark": "compute_features_grouped",
        "cases": [
            {
                "rows": args.rows,
                "runs": args.runs,
                "groups": group_results,
            }
        ],
    }

    out_file.write_text(json.dumps(result, indent=2))
    print(f"[benchmark] Saved → {out_file}")


if __name__ == "__main__":
    main()
