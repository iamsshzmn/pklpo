"""
Unit тесты для OHLCVAligner.

Проверяет синхронизацию нормализации с фактическими барами OHLCV.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

from src.market_meta_backup.infrastructure.ohlcv_aligner import OHLCVAligner


class TestOHLCVAligner:
    """Тесты для OHLCVAligner"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.engine = Mock()
        self.conn = Mock()
        self.engine.connect.return_value = self.conn
        self.conn.__enter__ = Mock(return_value=self.conn)
        self.conn.__exit__ = Mock(return_value=None)
        self.aligner = OHLCVAligner(self.engine)

    def test_load_bar_timestamps_basic(self):
        """Тест загрузки timestamps баров"""
        # Мокаем результат запроса
        mock_result = Mock()
        mock_result.__iter__ = Mock(
            return_value=iter(
                [
                    (1700000000000,),  # 2023-11-14 22:13:20
                    (1700000060000,),  # +1 минута
                    (1700000120000,),  # +2 минуты
                ]
            )
        )
        self.conn.execute.return_value = mock_result

        timestamps = self.aligner.load_bar_timestamps(
            symbol="BTC-USDT-SWAP", timeframe="1m"
        )

        assert len(timestamps) == 3
        assert isinstance(timestamps[0], datetime)
        assert timestamps[0] == datetime.fromtimestamp(1700000000)
        assert timestamps[1] == datetime.fromtimestamp(1700000060)
        assert timestamps[2] == datetime.fromtimestamp(1700000120)

    def test_load_bar_timestamps_with_time_range(self):
        """Тест загрузки с фильтром по времени"""
        start_time = datetime(2023, 11, 14, 22, 13, 20)
        end_time = datetime(2023, 11, 14, 22, 15, 20)

        mock_result = Mock()
        mock_result.__iter__ = Mock(
            return_value=iter(
                [
                    (int(start_time.timestamp() * 1000),),
                    (int((start_time + timedelta(minutes=1)).timestamp() * 1000),),
                ]
            )
        )
        self.conn.execute.return_value = mock_result

        timestamps = self.aligner.load_bar_timestamps(
            symbol="BTC-USDT-SWAP",
            timeframe="1m",
            start_time=start_time,
            end_time=end_time,
        )

        assert len(timestamps) == 2
        # Проверяем, что запрос был с правильными параметрами
        call_args = self.conn.execute.call_args
        assert "start_ms" in call_args[1] or "start_ms" in str(call_args)

    def test_load_bar_timestamps_cache(self):
        """Тест кэширования timestamps"""
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([(1700000000000,)]))
        self.conn.execute.return_value = mock_result

        # Первый вызов - загружает из БД
        timestamps1 = self.aligner.load_bar_timestamps(
            symbol="BTC-USDT-SWAP", timeframe="1m"
        )

        # Второй вызов - использует кэш
        timestamps2 = self.aligner.load_bar_timestamps(
            symbol="BTC-USDT-SWAP", timeframe="1m"
        )

        assert timestamps1 == timestamps2
        # Проверяем, что execute был вызван только один раз
        assert self.conn.execute.call_count == 1

    def test_align_to_bar_nearest(self):
        """Тест привязки к ближайшему бару (nearest strategy)"""
        bar_timestamps = [
            datetime(2023, 11, 14, 22, 13, 0),
            datetime(2023, 11, 14, 22, 14, 0),
            datetime(2023, 11, 14, 22, 15, 0),
        ]

        # Точное совпадение
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 14, 0), bar_timestamps, strategy="nearest"
        )
        assert result == datetime(2023, 11, 14, 22, 14, 0)

        # Ближе к предыдущему (25 секунд до 22:13:00, 35 секунд до 22:14:00)
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 13, 25), bar_timestamps, strategy="nearest"
        )
        assert result == datetime(2023, 11, 14, 22, 13, 0)

        # Ближе к следующему
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 13, 45), bar_timestamps, strategy="nearest"
        )
        assert result == datetime(2023, 11, 14, 22, 14, 0)

    def test_align_to_bar_floor(self):
        """Тест привязки к предыдущему бару (floor strategy)"""
        bar_timestamps = [
            datetime(2023, 11, 14, 22, 13, 0),
            datetime(2023, 11, 14, 22, 14, 0),
            datetime(2023, 11, 14, 22, 15, 0),
        ]

        # Точное совпадение
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 14, 0), bar_timestamps, strategy="floor"
        )
        assert result == datetime(2023, 11, 14, 22, 13, 0)

        # Между барами
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 14, 30), bar_timestamps, strategy="floor"
        )
        assert result == datetime(2023, 11, 14, 22, 14, 0)

        # До первого бара
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 12, 0), bar_timestamps, strategy="floor"
        )
        assert result is None

    def test_align_to_bar_ceil(self):
        """Тест привязки к следующему бару (ceil strategy)"""
        bar_timestamps = [
            datetime(2023, 11, 14, 22, 13, 0),
            datetime(2023, 11, 14, 22, 14, 0),
            datetime(2023, 11, 14, 22, 15, 0),
        ]

        # Точное совпадение
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 14, 0), bar_timestamps, strategy="ceil"
        )
        assert result == datetime(2023, 11, 14, 22, 14, 0)

        # Между барами
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 13, 30), bar_timestamps, strategy="ceil"
        )
        assert result == datetime(2023, 11, 14, 22, 14, 0)

        # После последнего бара
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 16, 0), bar_timestamps, strategy="ceil"
        )
        assert result is None

    def test_align_to_bar_empty_list(self):
        """Тест привязки к пустому списку баров"""
        result = self.aligner.align_to_bar(
            datetime(2023, 11, 14, 22, 14, 0), [], strategy="nearest"
        )
        assert result is None

    def test_clear_cache(self):
        """Тест очистки кэша"""
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([(1700000000000,)]))
        self.conn.execute.return_value = mock_result

        # Загружаем и кэшируем
        self.aligner.load_bar_timestamps(symbol="BTC-USDT-SWAP", timeframe="1m")
        assert "BTC-USDT-SWAP:1m" in self.aligner._bar_cache

        # Очищаем кэш
        self.aligner.clear_cache(symbol="BTC-USDT-SWAP", timeframe="1m")
        assert "BTC-USDT-SWAP:1m" not in self.aligner._bar_cache

        # Очищаем весь кэш
        self.aligner.load_bar_timestamps(symbol="ETH-USDT-SWAP", timeframe="1m")
        self.aligner.clear_cache()
        assert len(self.aligner._bar_cache) == 0
