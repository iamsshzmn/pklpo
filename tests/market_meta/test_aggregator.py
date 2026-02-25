"""
Unit тесты для MarketDataAggregator.

Проверяет агрегацию расширенных данных для разных таймфреймов.
"""

from datetime import datetime
from unittest.mock import Mock

import pandas as pd

from src.market_meta.infrastructure.aggregator import MarketDataAggregator
from src.market_meta.infrastructure.ohlcv_aligner import OHLCVAligner


class TestMarketDataAggregator:
    """Тесты для MarketDataAggregator"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.mock_engine = Mock()
        self.aligner = OHLCVAligner(self.mock_engine)
        self.aggregator = MarketDataAggregator(self.aligner)

        # Создаем тестовые данные 1m
        self.test_data_1m = pd.DataFrame(
            {
                "bar_timestamp": [
                    datetime(2023, 11, 14, 22, 13, 0),
                    datetime(2023, 11, 14, 22, 14, 0),
                    datetime(2023, 11, 14, 22, 15, 0),
                    datetime(2023, 11, 14, 22, 16, 0),
                    datetime(2023, 11, 14, 22, 17, 0),
                ],
                "symbol": ["BTC-USDT-SWAP"] * 5,
                "timeframe": ["1m"] * 5,
                "open_interest": [
                    1000000.0,
                    1000100.0,
                    1000200.0,
                    1000300.0,
                    1000400.0,
                ],
                "funding_rate": [0.0001, 0.0001, 0.0001, 0.0001, 0.0001],
                "bid_imbalance": [0.6, 0.61, 0.62, 0.63, 0.64],
                "source": ["okx"] * 5,
            }
        )

        # Мокаем загрузку баров 5m
        self.bar_timestamps_5m = [
            datetime(2023, 11, 14, 22, 15, 0),
            datetime(2023, 11, 14, 22, 20, 0),
        ]
        self.aligner.load_bar_timestamps = Mock(return_value=self.bar_timestamps_5m)

    def test_aggregate_1m_to_5m_oi(self):
        """Тест агрегации OI от 1m к 5m"""
        result = self.aggregator.aggregate_1m_to_timeframe(
            data=self.test_data_1m,
            symbol="BTC-USDT-SWAP",
            target_timeframe="5m",
        )

        assert not result.empty
        assert len(result) <= len(self.bar_timestamps_5m)
        assert "open_interest" in result.columns
        # Проверяем, что последнее значение в интервале
        assert (
            result["open_interest"].iloc[0] == 1000200.0
        )  # Последнее значение в первом интервале

    def test_aggregate_1m_to_5m_funding(self):
        """Тест агрегации funding rates от 1m к 5m"""
        result = self.aggregator.aggregate_1m_to_timeframe(
            data=self.test_data_1m,
            symbol="BTC-USDT-SWAP",
            target_timeframe="5m",
        )

        assert not result.empty
        assert "funding_rate" in result.columns

    def test_aggregate_1m_to_5m_l2(self):
        """Тест агрегации L2 данных от 1m к 5m"""
        result = self.aggregator.aggregate_1m_to_timeframe(
            data=self.test_data_1m,
            symbol="BTC-USDT-SWAP",
            target_timeframe="5m",
        )

        assert not result.empty
        assert "bid_imbalance" in result.columns
        assert "ask_imbalance" not in result.columns  # Нет в тестовых данных
        # Проверяем, что последнее значение в интервале
        assert (
            result["bid_imbalance"].iloc[0] == 0.62
        )  # Последнее значение в первом интервале

    def test_aggregate_empty_data(self):
        """Тест агрегации пустых данных"""
        empty_df = pd.DataFrame()
        result = self.aggregator.aggregate_1m_to_timeframe(
            data=empty_df, symbol="BTC-USDT-SWAP", target_timeframe="5m"
        )

        assert result.empty

    def test_aggregate_no_bar_timestamps(self):
        """Тест агрегации когда нет баров целевого таймфрейма"""
        self.aligner.load_bar_timestamps = Mock(return_value=[])

        result = self.aggregator.aggregate_1m_to_timeframe(
            data=self.test_data_1m, symbol="BTC-USDT-SWAP", target_timeframe="5m"
        )

        assert result.empty

    def test_aggregate_with_time_range(self):
        """Тест агрегации с указанием временного диапазона"""
        start_time = datetime(2023, 11, 14, 22, 13, 0)
        end_time = datetime(2023, 11, 14, 22, 17, 0)

        result = self.aggregator.aggregate_1m_to_timeframe(
            data=self.test_data_1m,
            symbol="BTC-USDT-SWAP",
            target_timeframe="5m",
            start_time=start_time,
            end_time=end_time,
        )

        # Проверяем, что load_bar_timestamps был вызван с правильными параметрами
        self.aligner.load_bar_timestamps.assert_called_once()
        call_args = self.aligner.load_bar_timestamps.call_args
        assert call_args[1]["start_time"] == start_time
        assert call_args[1]["end_time"] == end_time

    def test_aggregate_index_as_bar_timestamp(self):
        """Тест агрегации когда bar_timestamp в индексе"""
        data_with_index = self.test_data_1m.set_index("bar_timestamp")
        result = self.aggregator.aggregate_1m_to_timeframe(
            data=data_with_index, symbol="BTC-USDT-SWAP", target_timeframe="5m"
        )

        assert not result.empty
