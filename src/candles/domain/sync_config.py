from __future__ import annotations

import os

from pydantic import BaseModel, Field

from src.candles.domain.timeframes import TF_TO_MS

SWAP_BARS = list(TF_TO_MS.keys())


class SyncConfig(BaseModel, frozen=True):
    """Immutable, validated sync configuration.

    Fail-fast: invalid values raise ``ValidationError`` immediately.
    """

    max_requests_per_second: int = Field(80, ge=1, le=200)
    batch_size: int = Field(300, ge=50, le=1000)
    max_retries: int = Field(3, ge=0, le=10)
    retry_delay: float = Field(1.0, ge=0.1, le=30.0)
    timeout_seconds: float = Field(30.0, gt=0.0, le=300.0)
    max_concurrent_symbols: int = Field(3, ge=1, le=50)
    extra_data: bool = False
    use_ccxt: bool = True
    dynamic_batch_size: bool = False

    @classmethod
    def from_env(cls, overrides: dict | None = None) -> SyncConfig:
        """Build config from environment variables with optional overrides.

        Env vars: CANDLES_BATCH_SIZE, CANDLES_MAX_RETRIES, etc.
        Raises ``ValidationError`` on invalid values (fail-fast).
        """
        env_map: dict[str, str] = {
            "max_requests_per_second": "CANDLES_MAX_RPS",
            "batch_size": "CANDLES_BATCH_SIZE",
            "max_retries": "CANDLES_MAX_RETRIES",
            "retry_delay": "CANDLES_RETRY_DELAY",
            "timeout_seconds": "OKX_TIMEOUT_SECONDS",
            "max_concurrent_symbols": "CANDLES_MAX_CONCURRENT",
            "extra_data": "CANDLES_EXTRA_DATA",
            "use_ccxt": "CANDLES_USE_CCXT",
            "dynamic_batch_size": "CANDLES_DYNAMIC_BATCH",
        }
        values: dict[str, object] = {}
        for field_name, env_var in env_map.items():
            raw = os.environ.get(env_var)
            if raw is not None:
                values[field_name] = raw
        if overrides:
            values.update(overrides)
        return cls(**values)


# Convenience dict for runtime callers that still pass plain mappings
DEFAULT_CONFIG: dict[str, int | float | bool] = SyncConfig().model_dump()

__all__ = ["DEFAULT_CONFIG", "SWAP_BARS", "SyncConfig"]
