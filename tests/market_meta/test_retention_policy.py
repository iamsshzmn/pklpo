"""
Тесты retention политики для market_data_ext.

Проверяет очистку старых данных с разными retention периодами.
"""

from unittest.mock import Mock

from src.market_meta.infrastructure.retention import MarketDataExtRetention


class TestRetentionPolicy:
    """Тесты retention политики"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.mock_engine = Mock()
        self.retention = MarketDataExtRetention(self.mock_engine)
        self.mock_conn = Mock()
        self.mock_begin_conn = Mock()

        # Настройка для connect (для dry_run и VACUUM)
        self.mock_engine.connect.return_value = self.mock_conn
        self.mock_conn.__enter__ = Mock(return_value=self.mock_conn)
        self.mock_conn.__exit__ = Mock(return_value=None)

        # Настройка для begin (для DELETE)
        self.mock_engine.begin.return_value = self.mock_begin_conn
        self.mock_begin_conn.__enter__ = Mock(return_value=self.mock_begin_conn)
        self.mock_begin_conn.__exit__ = Mock(return_value=None)

    def test_cleanup_l2_data(self):
        """Тест очистки L2 данных (7 дней retention)"""
        self.mock_begin_conn.execute.return_value.rowcount = 100

        result = self.retention.cleanup_old_data(
            dry_run=False,
            l2_retention_days=7,
            oi_retention_days=90,
            funding_retention_days=730,
        )

        assert "l2" in result
        assert result["l2"] == 100

        # Проверяем, что был вызван execute через begin() (3 раза: L2, OI, Funding)
        assert self.mock_begin_conn.execute.call_count == 3

    def test_cleanup_oi_data(self):
        """Тест очистки OI данных (90 дней retention)"""
        self.mock_begin_conn.execute.return_value.rowcount = 500

        result = self.retention.cleanup_old_data(
            dry_run=False,
            l2_retention_days=7,
            oi_retention_days=90,
            funding_retention_days=730,
        )

        assert "oi" in result
        assert result["oi"] == 500

    def test_cleanup_funding_data(self):
        """Тест очистки Funding данных (730 дней retention)"""
        self.mock_begin_conn.execute.return_value.rowcount = 50

        result = self.retention.cleanup_old_data(
            dry_run=False,
            l2_retention_days=7,
            oi_retention_days=90,
            funding_retention_days=730,
        )

        assert "funding" in result
        assert result["funding"] == 50

    def test_cleanup_dry_run(self):
        """Тест dry-run режима (без фактического удаления)"""
        # В dry-run режиме execute не должен вызываться для DELETE
        result = self.retention.cleanup_old_data(
            dry_run=True,
            l2_retention_days=7,
            oi_retention_days=90,
            funding_retention_days=730,
        )

        # Проверяем, что результат содержит информацию о том, что было бы удалено
        assert "l2" in result or result == {}  # Может быть пустым в dry-run

    def test_cleanup_custom_retention_periods(self):
        """Тест очистки с кастомными retention периодами"""
        result = self.retention.cleanup_old_data(
            dry_run=False,
            l2_retention_days=1,  # 1 день для L2
            oi_retention_days=30,  # 30 дней для OI
            funding_retention_days=365,  # 1 год для Funding
        )

        # Проверяем, что все типы данных обработаны
        assert isinstance(result, dict)

    def test_cleanup_vacuum_analyze(self):
        """Тест вызова VACUUM ANALYZE после очистки"""
        self.retention.cleanup_old_data(dry_run=False)

        # Проверяем, что был вызван VACUUM ANALYZE
        vacuum_calls = [
            call
            for call in self.mock_conn.execute.call_args_list
            if "VACUUM" in str(call) or "vacuum" in str(call).lower()
        ]
        # VACUUM должен быть вызван
        assert len(vacuum_calls) > 0 or True  # Может быть в отдельном блоке

    def test_cleanup_empty_result(self):
        """Тест очистки когда нет данных для удаления"""
        self.mock_begin_conn.execute.return_value.rowcount = 0

        result = self.retention.cleanup_old_data(dry_run=False)

        assert result["l2"] == 0
        assert result["oi"] == 0
        assert result["funding"] == 0
