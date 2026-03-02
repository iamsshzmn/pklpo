from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from src.features.application import feature_window as fw


def _result(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


@pytest.mark.asyncio
async def test_check_has_new_ohlcv_no_rows() -> None:
    session = AsyncMock()
    session.execute.return_value = _result(None)

    has_new, latest_ts = await fw.check_has_new_ohlcv(
        session,
        "BTC-USDT-SWAP",
        "1m",
        None,
    )

    assert has_new is False
    assert latest_ts is None


@pytest.mark.asyncio
async def test_check_has_new_ohlcv_first_run() -> None:
    session = AsyncMock()
    session.execute.return_value = _result(1_700_000_000_000)

    has_new, latest_ts = await fw.check_has_new_ohlcv(
        session,
        "BTC-USDT-SWAP",
        "1m",
        None,
    )

    assert has_new is True
    assert latest_ts == 1_700_000_000


@pytest.mark.asyncio
async def test_get_ohlcv_window_applies_warmup_and_normalizes(monkeypatch) -> None:
    captured = {}

    async def _fake_fetch(session, symbol, timeframe, since_ts=None, limit=200):
        captured["since_ts"] = since_ts
        captured["limit"] = limit
        return pd.DataFrame(
            [
                {
                    "ts": 1_700_000_000,
                    "open": 1.0,
                    "high": 2.0,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 10.0,
                }
            ]
        )

    monkeypatch.setattr(fw, "fetch_ohlcv_df", _fake_fetch)

    session = AsyncMock()
    df = await fw.get_ohlcv_window(
        session,
        "BTC-USDT-SWAP",
        "1m",
        from_ts=1_700_000_600,
        warmup_bars=5,
    )

    assert captured["since_ts"] == 1_700_000_300
    assert captured["limit"] == fw.limit_for_timeframe("1m")
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert int(df.iloc[0]["timestamp"]) == 1_700_000_000_000
