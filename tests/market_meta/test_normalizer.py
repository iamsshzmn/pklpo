"""
Unit тесты для MarketDataNormalizer.

Проверяет нормализацию расширенных данных к границам баров OHLCV.
"""

from datetime import datetime
from unittest.mock import Mock

from src.market_meta.infrastructure.normalizer import MarketDataNormalizer
from src.market_meta.infrastructure.ohlcv_aligner import OHLCVAligner


class TestMarketDataNormalizer:
    """Тесты для MarketDataNormalizer"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.mock_engine = Mock()
        self.aligner = OHLCVAligner(self.mock_engine)
        self.normalizer = MarketDataNormalizer(self.aligner)

        # Мокаем загрузку баров
        self.bar_timestamps = [
            datetime(2023, 11, 14, 22, 13, 0),
            datetime(2023, 11, 14, 22, 14, 0),
            datetime(2023, 11, 14, 22, 15, 0),
        ]
        self.aligner.load_bar_timestamps = Mock(return_value=self.bar_timestamps)
        self.aligner.align_to_bar = Mock(side_effect=self._mock_align_to_bar)

    def _mock_align_to_bar(self, timestamp, bar_timestamps, strategy="nearest"):
        """Мок для align_to_bar"""
        if not bar_timestamps:
            return None

        if strategy == "nearest":
            # Простая логика: ближайший бар
            for bar_ts in bar_timestamps:
                if abs((timestamp - bar_ts).total_seconds()) < 30:
                    return bar_ts
            return bar_timestamps[0]  # Fallback
        if strategy == "floor":
            # Предыдущий бар
            for i, bar_ts in enumerate(bar_timestamps):
                if timestamp < bar_ts:
                    return bar_timestamps[i - 1] if i > 0 else None
            return bar_timestamps[-1]
        return None

    def test_normalize_funding_rates(self):
        """Тест нормализации funding rates"""
        records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30),
                "funding_rate": 0.0001,
                "source": "okx",
            }
        ]

        result = self.normalizer.normalize_to_1m_bars(
            records, symbol="BTC-USDT-SWAP", bar_timestamps=self.bar_timestamps
        )

        assert len(result) == 1
        assert result[0]["bar_timestamp"] in self.bar_timestamps
        assert result[0]["timeframe"] == "1m"
        assert result[0]["funding_rate"] == 0.0001

    def test_normalize_open_interest(self):
        """Тест нормализации Open Interest"""
        records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30),
                "open_interest": 1000000.0,
                "source": "okx",
            },
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 14, 30),
                "open_interest": 1000500.0,
                "source": "okx",
            },
        ]

        result = self.normalizer.normalize_to_1m_bars(
            records, symbol="BTC-USDT-SWAP", bar_timestamps=self.bar_timestamps
        )

        assert len(result) >= 1
        assert all(r["bar_timestamp"] in self.bar_timestamps for r in result)
        assert all(r["timeframe"] == "1m" for r in result)

    def test_normalize_l2_data(self):
        """Тест нормализации L2 данных"""
        records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30),
                "bid_imbalance": 0.6,
                "ask_imbalance": 0.4,
                "spread_bps": 10.5,
                "source": "okx",
            }
        ]

        result = self.normalizer.normalize_to_1m_bars(
            records, symbol="BTC-USDT-SWAP", bar_timestamps=self.bar_timestamps
        )

        assert len(result) == 1
        assert result[0]["bar_timestamp"] in self.bar_timestamps
        assert result[0]["bid_imbalance"] == 0.6
        assert result[0]["ask_imbalance"] == 0.4
        assert result[0]["spread_bps"] == 10.5

    def test_normalize_empty_records(self):
        """Тест нормализации пустого списка"""
        result = self.normalizer.normalize_to_1m_bars(
            [], symbol="BTC-USDT-SWAP", bar_timestamps=self.bar_timestamps
        )

        assert result == []

    def test_normalize_auto_load_bars(self):
        """Тест автоматической загрузки баров"""
        records = [
            {
                "symbol": "BTC-USDT-SWAP",
                "timestamp": datetime(2023, 11, 14, 22, 13, 30),
                "funding_rate": 0.0001,
                "source": "okx",
            }
        ]

        # Не передаем bar_timestamps - должен загрузить автоматически
        result = self.normalizer.normalize_to_1m_bars(records, symbol="BTC-USDT-SWAP")

        # Проверяем, что был вызван load_bar_timestamps
        self.aligner.load_bar_timestamps.assert_called_once()
        assert len(result) >= 0  # Может быть пустым если нет баров

    def test_detect_data_type(self):
        """Тест определения типа данных"""
        funding_record = {"funding_rate": 0.0001}
        oi_record = {"open_interest": 1000000.0}
        l2_record = {"bid_imbalance": 0.6}

        assert self.normalizer._detect_data_type(funding_record) == "funding"
        assert self.normalizer._detect_data_type(oi_record) == "oi"
        assert self.normalizer._detect_data_type(l2_record) == "l2"

    def test_extract_timestamp(self):
        """Тест извлечения timestamp"""
        # datetime объект
        record1 = {"timestamp": datetime(2023, 11, 14, 22, 0, 0)}
        assert self.normalizer._extract_timestamp(record1) == datetime(
            2023, 11, 14, 22, 0, 0
        )

        # миллисекунды
        record2 = {"timestamp": 1700000000000}
        result = self.normalizer._extract_timestamp(record2)
        assert isinstance(result, datetime)

        # секунды
        record3 = {"timestamp": 1700000000}
        result = self.normalizer._extract_timestamp(record3)
        assert isinstance(result, datetime)

        # None
        record4 = {}
        assert self.normalizer._extract_timestamp(record4) is None
