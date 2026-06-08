from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest


def _make_ohlcv_df(n: int = 25) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": range(n),
            "open": [1.0] * n,
            "high": [1.1] * n,
            "low": [0.9] * n,
            "close": [1.0] * n,
            "volume": [100.0] * n,
        }
    )


def _make_features_df(n: int = 25) -> pd.DataFrame:
    df = _make_ohlcv_df(n)
    df["ema_8"] = [1.0] * n
    df["rsi_14"] = [50.0] * n
    return df


class TestProcessSinglePair:
    @pytest.mark.asyncio
    async def test_process_single_pair_delegates_persistence_to_save_use_case(
        self,
        monkeypatch,
    ):
        from src.features.application.batch_processor import process_single_pair

        session = AsyncMock()
        ohlcv_df = _make_ohlcv_df()
        features_df = _make_features_df()
        save_deps = SimpleNamespace(repository=object(), observer=object())

        monkeypatch.setattr(
            "src.features.application.batch_processor.get_max_lookback_for_strategies",
            MagicMock(return_value=100),
        )
        monkeypatch.setattr(
            "src.features.application.batch_processor.timeframe_to_seconds",
            MagicMock(return_value=60),
        )
        fetch_ohlcv_df = AsyncMock(return_value=ohlcv_df)
        calculate_batch = MagicMock(return_value=features_df)
        monkeypatch.setattr(
            "src.features.application.batch_processor.calculate_batch",
            calculate_batch,
        )
        ensure_columns_exist = AsyncMock()
        create_save_deps = MagicMock(return_value=save_deps)
        save_batch = AsyncMock(
            return_value={"success": True, "rows_saved": len(features_df)}
        )
        monkeypatch.setattr(
            "src.features.application.batch_processor.save_batch",
            save_batch,
        )
        storage_gateway = SimpleNamespace(
            fetch_latest_ts=AsyncMock(return_value=1_000),
            fetch_ohlcv_df=fetch_ohlcv_df,
            ensure_indicator_columns=ensure_columns_exist,
        )

        success, rows_saved, duration, errors = await process_single_pair(
            session=session,
            symbol="BTC",
            timeframe="1m",
            available={"ema_8", "rsi_14"},
            storage_gateway=storage_gateway,
            save_dependencies_factory=create_save_deps,
        )

        assert success is True
        assert rows_saved == len(features_df)
        assert duration >= 0
        assert errors == []

        fetch_ohlcv_df.assert_awaited_once_with(
            session,
            "BTC",
            "1m",
            since_ts=0,
        )
        calculate_batch.assert_called_once_with(
            ohlcv_df,
            available={"ema_8", "rsi_14"},
            volatility_normalize=False,
        )
        ensure_columns_exist.assert_awaited_once_with(
            session,
            "indicators_p",
            ["ema_8", "rsi_14"],
        )
        create_save_deps.assert_called_once_with(session)
        save_batch.assert_awaited_once()
        save_kwargs = save_batch.await_args.kwargs
        assert save_kwargs["session"] is session
        assert save_kwargs["df"] is features_df
        assert save_kwargs["symbol"] == "BTC"
        assert save_kwargs["timeframe"] == "1m"
        assert save_kwargs["repository"] is save_deps.repository
        assert save_kwargs["observer"] is save_deps.observer

    @pytest.mark.asyncio
    async def test_process_single_pair_returns_insufficient_data_error(
        self,
        monkeypatch,
    ):
        from src.features.application.batch_processor import process_single_pair

        session = AsyncMock()

        monkeypatch.setattr(
            "src.features.application.batch_processor.get_max_lookback_for_strategies",
            MagicMock(return_value=50),
        )
        monkeypatch.setattr(
            "src.features.application.batch_processor.timeframe_to_seconds",
            MagicMock(return_value=60),
        )
        save_batch = AsyncMock()
        monkeypatch.setattr(
            "src.features.application.batch_processor.save_batch",
            save_batch,
        )
        storage_gateway = SimpleNamespace(
            fetch_latest_ts=AsyncMock(return_value=0),
            fetch_ohlcv_df=AsyncMock(return_value=_make_ohlcv_df(10)),
            ensure_indicator_columns=AsyncMock(),
        )

        success, rows_saved, duration, errors = await process_single_pair(
            session=session,
            symbol="BTC",
            timeframe="1m",
            available={"ema_8"},
            storage_gateway=storage_gateway,
            save_dependencies_factory=MagicMock(),
        )

        assert success is False
        assert rows_saved == 0
        assert duration >= 0
        assert errors == ["Insufficient data"]
        save_batch.assert_not_awaited()
