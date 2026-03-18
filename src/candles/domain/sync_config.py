from __future__ import annotations

from src.candles.domain.timeframes import TF_TO_MS

SWAP_BARS = list(TF_TO_MS.keys())

DEFAULT_CONFIG: dict[str, int | float | bool] = {
    "max_requests_per_second": 80,
    "batch_size": 300,
    "max_retries": 3,
    "retry_delay": 1.0,
    "max_concurrent_symbols": 3,
    "extra_data": False,
    "use_ccxt": True,
    "dynamic_batch_size": False,
}

__all__ = ["DEFAULT_CONFIG", "SWAP_BARS"]
