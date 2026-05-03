"""
Интеграционные тесты нормализации и агрегации.

Проверяет полный цикл: загрузка → нормализация → агрегация.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pandas as pd

from src.market_meta_backup.infrastructure.aggregator import MarketDataAggregator
from src.market_meta_backup.infrastructure.normalizer import MarketDataNormalizer
from src.market_meta_backup.infrastructure.ohlcv_aligner import OHLCVAligner


class TestIntegrationNormalization:
    """Интеграционные тесты нормализации"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.mock_engine = Mock()
        self.aligner = OHLCVAligner(self.mock_engine)
        self.normalizer = MarketDataNormalizer(self.aligner)
        self.aggregator = MarketDataAggregator(self.aligner)

        # Мокаем бары OHLCV
        self.bar_timestamps_1m = [
            datetime(2023, 11, 14, 22, 13, 0) + timedelta(minutes=i) for i in range(10)
        ]
        self.bar_timestamps_5m = [
            datetime(2023, 11, 14, 22, 15, 0) + timedelta(minutes=5 * i)
            for i in range(2)
        ]

        self.aligner.load_bar_timestamps = Mock(
            side_effect=lambda symbol, timeframe, **kwargs: (
                self.bar_timestamps_1m if timeframe == "1m" else self.bar_timestamps_5m
            )
        )

        # Мокаем align_to_bar
        def mock_align(timestamp, bar_timestamps, strategy="nearest"):
            if not bar_timestamps:
                return None
            if strategy == "nearest":
                # Ближайший бар
                min_diff = min(
                    abs((timestamp - ts).total_seconds()) for ts in bar_timestamps
                )
                for ts in bar_timestamps:
                    if abs((timestamp - ts).total_seconds()) == min_diff:
                        return ts
            elif strategy == "floor":
                # Предыдущий бар
                for i, ts in enumerate(bar_timestamps):
                    if timestamp < ts:
                        return bar_timestamps[i - 1] if i > 0 else None
                return bar_timestamps[-1]
            return bar_timestamps[0]

        self.aligner.align_to_bar = Mock(side_effect=mock_align)

    def test_full_cycle_funding_rates(self):
        """Полный цикл: загрузка funding → нормализация → агрегация"""
        # 1. Загружаем funding rates (мок)
        funding_records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30),
                "funding_rate": 0.0001,
                "next_funding_time": datetime(2023, 11, 15, 6, 0, 0),
                "funding_interval_hours": 8,
                "source": "okx",
            }
        ]

        # 2. Нормализуем к 1m барам
        normalized = self.normalizer.normalize_to_1m_bars(
            funding_records,
            symbol="BTC-USDT-SWAP",
            bar_timestamps=self.bar_timestamps_1m,
        )

        assert len(normalized) == 1
        assert normalized[0]["bar_timestamp"] in self.bar_timestamps_1m
        assert normalized[0]["timeframe"] == "1m"

        # 3. Агрегируем к 5m
        df_1m = pd.DataFrame(normalized)
        aggregated = self.aggregator.aggregate_1m_to_timeframe(
            df_1m, symbol="BTC-USDT-SWAP", target_timeframe="5m"
        )

        assert not aggregated.empty
        assert "funding_rate" in aggregated.columns

    def test_full_cycle_open_interest(self):
        """Полный цикл: загрузка OI → нормализация → агрегация"""
        # 1. Загружаем OI (мок)
        oi_records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30) + timedelta(minutes=i),
                "open_interest": 1000000.0 + i * 100,
                "source": "okx",
            }
            for i in range(5)
        ]

        # 2. Нормализуем к 1m барам
        normalized = self.normalizer.normalize_to_1m_bars(
            oi_records, symbol="BTC-USDT-SWAP", bar_timestamps=self.bar_timestamps_1m
        )

        assert len(normalized) > 0
        assert all(r["bar_timestamp"] in self.bar_timestamps_1m for r in normalized)

        # 3. Агрегируем к 5m
        df_1m = pd.DataFrame(normalized)
        aggregated = self.aggregator.aggregate_1m_to_timeframe(
            df_1m, symbol="BTC-USDT-SWAP", target_timeframe="5m"
        )

        assert not aggregated.empty
        assert "open_interest" in aggregated.columns
        # Проверяем, что последнее значение в интервале
        # Первый 5m бар (22:15:00) включает данные от начала до 22:15:00
        # Последнее значение в этом интервале будет для 22:15:00 (i=2, значение 1000200.0)
        assert aggregated["open_interest"].iloc[0] == 1000200.0

    def test_full_cycle_l2_data(self):
        """Полный цикл: загрузка L2 → нормализация → агрегация"""
        # 1. Загружаем L2 (мок)
        l2_records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30) + timedelta(minutes=i),
                "bid_imbalance": 0.6 + i * 0.01,
                "ask_imbalance": 0.4 - i * 0.01,
                "spread_bps": 10.0 + i,
                "source": "okx",
            }
            for i in range(5)
        ]

        # 2. Нормализуем к 1m барам
        normalized = self.normalizer.normalize_to_1m_bars(
            l2_records, symbol="BTC-USDT-SWAP", bar_timestamps=self.bar_timestamps_1m
        )

        assert len(normalized) > 0

        # 3. Агрегируем к 5m
        df_1m = pd.DataFrame(normalized)
        aggregated = self.aggregator.aggregate_1m_to_timeframe(
            df_1m, symbol="BTC-USDT-SWAP", target_timeframe="5m"
        )

        assert not aggregated.empty
        assert "bid_imbalance" in aggregated.columns
        assert "spread_bps" in aggregated.columns

    def test_normalization_preserves_data_integrity(self):
        """Проверка сохранения целостности данных при нормализации"""
        records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30),
                "open_interest": 1000000.0,
                "source": "okx",
            }
        ]

        normalized = self.normalizer.normalize_to_1m_bars(
            records, symbol="BTC-USDT-SWAP", bar_timestamps=self.bar_timestamps_1m
        )

        # Проверяем, что данные не потеряны
        assert len(normalized) > 0
        assert normalized[0]["open_interest"] == 1000000.0
        assert normalized[0]["symbol"] == "BTC-USDT-SWAP"
        assert normalized[0]["source"] == "okx"

    def test_aggregation_uses_last_value(self):
        """Проверка, что агрегация использует последнее значение в интервале"""
        # Создаем данные с несколькими значениями в одном интервале
        df_1m = pd.DataFrame(
            {
                "bar_timestamp": [
                    datetime(2023, 11, 14, 22, 13, 0),
                    datetime(2023, 11, 14, 22, 14, 0),
                    datetime(2023, 11, 14, 22, 15, 0),
                ],
                "open_interest": [1000000.0, 1000100.0, 1000200.0],
                "symbol": ["BTC-USDT-SWAP"] * 3,
                "timeframe": ["1m"] * 3,
                "source": ["okx"] * 3,
            }
        )

        aggregated = self.aggregator.aggregate_1m_to_timeframe(
            df_1m, symbol="BTC-USDT-SWAP", target_timeframe="5m"
        )

        # Проверяем, что используется последнее значение
        assert not aggregated.empty
        # В первом интервале должно быть последнее значение (1000200.0)
        assert aggregated["open_interest"].iloc[0] == 1000200.0
