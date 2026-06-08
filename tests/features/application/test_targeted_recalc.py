from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from src.core.run_context import RunContext


@dataclass
class FetchStub:
    df: pd.DataFrame | None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def __call__(self, **kwargs: Any) -> pd.DataFrame | None:
        self.calls.append(kwargs)
        return self.df


@dataclass
class SaveStub:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def __call__(self, df: pd.DataFrame, symbol: str, timeframe: str) -> int:
        self.calls.append(
            {"df": df.copy(), "symbol": symbol, "timeframe": timeframe},
        )
        return len(df)


def _ctx() -> RunContext:
    return RunContext(
        run_id="recalc-run",
        algo_version="features-v1",
        params_hash="params-123",
        created_at=datetime(2026, 5, 7, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_recalc_in_range_fetches_with_warmup_and_until_ts_then_saves_target_rows() -> (
    None
):
    from src.features.application.targeted_recalc import RecalcFeaturesInRange

    fetch = FetchStub(
        pd.DataFrame(
            [
                {"ts": 100, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10},
                {"ts": 160, "open": 2, "high": 3, "low": 2, "close": 3, "volume": 11},
                {"ts": 220, "open": 3, "high": 4, "low": 3, "close": 4, "volume": 12},
            ]
        )
    )
    save = SaveStub()
    use_case = RecalcFeaturesInRange(
        fetch_ohlcv_df=fetch,
        save_features_df=save,
        compute_features_fn=lambda df, specs: df.assign(rsi=42.0),
        specs=["rsi"],
        warmup_bars=2,
    )

    outcome = await use_case.recalc_in_range(
        symbol="BTC-USDT-SWAP",
        tf="1m",
        start_ts_ms=160_000,
        end_ts_ms=240_000,
        run_context=_ctx(),
    )

    assert fetch.calls == [
        {
            "symbol": "BTC-USDT-SWAP",
            "timeframe": "1m",
            "since_ts": 40,
            "until_ts": 240_000,
            "limit": 4,
        }
    ]
    assert outcome.rows_written == 2
    assert outcome.run_id == "recalc-run"
    assert outcome.algo_version == "features-v1"
    assert outcome.params_hash == "params-123"
    assert list(save.calls[0]["df"]["ts"]) == [160, 220]


@pytest.mark.asyncio
async def test_recalc_in_range_returns_zero_when_fetch_returns_no_rows() -> None:
    from src.features.application.targeted_recalc import RecalcFeaturesInRange

    fetch = FetchStub(None)
    save = SaveStub()
    use_case = RecalcFeaturesInRange(
        fetch_ohlcv_df=fetch,
        save_features_df=save,
        compute_features_fn=lambda df, specs: df,
        specs=["rsi"],
        warmup_bars=2,
    )

    outcome = await use_case.recalc_in_range(
        symbol="BTC-USDT-SWAP",
        tf="1H",
        start_ts_ms=7_200_000,
        end_ts_ms=10_800_000,
        run_context=_ctx(),
    )

    assert outcome.rows_written == 0
    assert save.calls == []


@pytest.mark.asyncio
async def test_recalc_in_range_blocks_when_warmup_window_has_gap() -> None:
    from src.features.application.targeted_recalc import RecalcFeaturesInRange

    fetch = FetchStub(
        pd.DataFrame(
            [
                {"ts": 100, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10},
                {"ts": 220, "open": 3, "high": 4, "low": 3, "close": 4, "volume": 12},
                {"ts": 280, "open": 4, "high": 5, "low": 4, "close": 5, "volume": 13},
            ]
        )
    )
    save = SaveStub()
    use_case = RecalcFeaturesInRange(
        fetch_ohlcv_df=fetch,
        save_features_df=save,
        compute_features_fn=lambda df, specs: df.assign(rsi=42.0),
        specs=["rsi"],
        warmup_bars=3,
    )

    outcome = await use_case.recalc_in_range(
        symbol="BTC-USDT-SWAP",
        tf="1m",
        start_ts_ms=220_000,
        end_ts_ms=300_000,
        run_context=_ctx(),
    )

    assert outcome.rows_written == 0
    assert save.calls == []
