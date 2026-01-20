"""Юнит-тесты для CombinationService."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from ..application.service import CombinationService
from ..domain.models import CombinationRow


@pytest.fixture()
def mock_provider() -> MagicMock:
    """Мок IndicatorProvider."""
    provider = MagicMock()
    provider.load_indicators = AsyncMock(
        return_value=pd.DataFrame(
            {
                "timestamp": [1609459200000, 1609459260000, 1609459320000],
                "rsi14": [50.0, 55.0, 60.0],
                "macd": [0.1, 0.2, 0.3],
                "macd_signal": [0.05, 0.15, 0.25],
            }
        )
    )
    return provider


@pytest.fixture()
def mock_calculator() -> MagicMock:
    """Мок CombinationCalculator."""
    calculator = MagicMock()

    def calculate_for_df(symbol: str, timeframe: str, df_indicators: pd.DataFrame):
        """Генерирует тестовые CombinationRow."""
        rows = []
        for _idx, row in df_indicators.iterrows():
            ts = datetime.fromtimestamp(row["timestamp"] / 1000.0)
            rows.append(
                CombinationRow(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=ts,
                    combination_id="macd_rsi",
                    features={
                        "direction_num": 1.0,
                        "trend_score": 0.75,
                        "signal_strength": 0.8,
                        "rsi_normalized": row["rsi14"] / 100.0,
                        "macd_direction_num": 1.0 if row["macd"] > 0 else -1.0,
                    },
                    meta=None,
                )
            )
        return iter(rows)

    calculator.calculate_for_df = calculate_for_df
    return calculator


@pytest.fixture()
def mock_repository() -> MagicMock:
    """Мок CombinationRepository."""
    repository = MagicMock()
    repository.upsert_batch = AsyncMock(return_value=3)
    return repository


@pytest.mark.asyncio()
async def test_compute_for_df(mock_provider, mock_calculator, mock_repository):
    """Тест compute_for_df."""
    service = CombinationService(
        provider=mock_provider,
        calculator=mock_calculator,
        repository=mock_repository,
    )

    df = pd.DataFrame(
        {
            "timestamp": [1609459200000, 1609459260000],
            "rsi14": [50.0, 55.0],
            "macd": [0.1, 0.2],
        }
    )

    rows = await service.compute_for_df("BTC-USDT", "1m", df)

    assert len(rows) == 2
    assert all(isinstance(row, CombinationRow) for row in rows)
    assert all(row.symbol == "BTC-USDT" for row in rows)
    assert all(row.timeframe == "1m" for row in rows)
    assert all(row.combination_id == "macd_rsi" for row in rows)
    assert all(isinstance(row.features, dict) for row in rows)
    assert all(
        all(isinstance(v, int | float) for v in row.features.values()) for row in rows
    )


@pytest.mark.asyncio()
async def test_compute_for_df_empty(mock_provider, mock_calculator, mock_repository):
    """Тест compute_for_df с пустым DataFrame (empty DataFrame)."""
    service = CombinationService(
        provider=mock_provider,
        calculator=mock_calculator,
        repository=mock_repository,
    )

    df = pd.DataFrame()

    rows = await service.compute_for_df("BTC-USDT", "1m", df)

    assert len(rows) == 0


@pytest.mark.asyncio()
async def test_compute_and_save_for_range(
    mock_provider, mock_calculator, mock_repository
):
    """Тест compute_and_save_for_range."""
    service = CombinationService(
        provider=mock_provider,
        calculator=mock_calculator,
        repository=mock_repository,
    )

    start = datetime(2025, 1, 1)
    end = datetime(2025, 1, 2)

    saved = await service.compute_and_save_for_range(
        symbol="BTC-USDT",
        timeframe="1m",
        start=start,
        end=end,
        limit=100,
    )

    assert saved == 3
    mock_provider.load_indicators.assert_called_once()
    mock_repository.upsert_batch.assert_called_once()


@pytest.mark.asyncio()
async def test_compute_and_save_latest(mock_provider, mock_calculator, mock_repository):
    """Тест compute_and_save_latest."""
    service = CombinationService(
        provider=mock_provider,
        calculator=mock_calculator,
        repository=mock_repository,
    )

    saved = await service.compute_and_save_latest(
        symbol="BTC-USDT",
        timeframe="1m",
        limit=500,
    )

    assert saved == 3
    mock_provider.load_indicators.assert_called_once()
    mock_repository.upsert_batch.assert_called_once()
