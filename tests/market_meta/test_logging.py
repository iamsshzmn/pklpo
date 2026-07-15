from unittest.mock import Mock, patch

import pytest

from src.market_meta_backup.infrastructure import logging_config as legacy_logging
from src.candles.infrastructure import logging_config as canonical_logging


def test_legacy_logging_module_aliases_canonical_module() -> None:
    assert legacy_logging.MarketMetaLogger is canonical_logging.MarketMetaLogger
    assert legacy_logging.configure_logging is canonical_logging.configure_logging
    assert legacy_logging._market_meta_logger is canonical_logging._market_meta_logger
    assert legacy_logging.DEFAULT_LOG_FILE == canonical_logging.DEFAULT_LOG_FILE


class TestMarketMetaLogger:
    def setup_method(self) -> None:
        self.logger = legacy_logging.MarketMetaLogger("test_logger")
        self.logger._configured = False

    def test_configure_marks_logger_as_configured(self) -> None:
        self.logger.configure(level="INFO", console_output=False, file_output=True)
        assert self.logger._configured is True
        assert self.logger.logger.name.endswith("test_logger")

    def test_get_logger_with_name(self) -> None:
        component_logger = self.logger.get_logger("api")
        assert component_logger.name.endswith("test_logger.api")

    def test_get_logger_without_name(self) -> None:
        main_logger = self.logger.get_logger()
        assert main_logger.name.endswith("test_logger")

    def test_log_validation_result_calls_underlying_logger(self) -> None:
        self.logger.logger.info = Mock()
        self.logger.logger.warning = Mock()

        self.logger.log_validation_result("BTC-USDT", [], ["warn"])
        self.logger.log_validation_result("BTC-USDT", ["violation"])

        assert self.logger.logger.info.called
        assert self.logger.logger.warning.called

    def test_log_cache_and_refresh_and_risk_emit_messages(self) -> None:
        self.logger.logger.info = Mock()
        self.logger.logger.warning = Mock()
        self.logger.logger.error = Mock()

        self.logger.log_cache_status(
            {"is_valid": True, "instruments_count": 10, "ttl_hours": 1.5}
        )
        self.logger.log_refresh_status(True, 10)
        self.logger.log_refresh_status(False, 0, "boom")
        self.logger.log_risk_check("BTC-USDT", "HIGH", "danger")
        self.logger.log_risk_check("BTC-USDT", "LOW", "ok")

        assert self.logger.logger.info.call_count >= 3
        assert self.logger.logger.warning.called
        assert self.logger.logger.error.called


class TestLoggingFunctions:
    def test_get_logger(self) -> None:
        logger = legacy_logging.get_logger("component")
        assert logger.name.endswith("market_meta.component")

    def test_module_level_helpers_delegate_to_global_logger(self) -> None:
        global_logger = legacy_logging._market_meta_logger
        global_logger.log_validation_result = Mock()
        global_logger.log_cache_status = Mock()
        global_logger.log_refresh_status = Mock()
        global_logger.log_risk_check = Mock()

        legacy_logging.log_validation_result("ETH-USDT", ["bad"])
        legacy_logging.log_cache_status({"is_valid": False})
        legacy_logging.log_refresh_status(True, 100)
        legacy_logging.log_risk_check("BTC-USDT", "CRITICAL", "risk")

        global_logger.log_validation_result.assert_called_once()
        global_logger.log_cache_status.assert_called_once()
        global_logger.log_refresh_status.assert_called_once()
        global_logger.log_risk_check.assert_called_once()

    def test_configure_logging_marks_global_logger_configured(self) -> None:
        legacy_logging._market_meta_logger._configured = False
        legacy_logging.configure_logging(level="DEBUG")
        assert legacy_logging._market_meta_logger._configured is True


class TestEnvironmentConfiguration:
    @patch("src.candles.infrastructure.logging_config.configure_logging")
    def test_auto_configure_defaults(self, mock_configure: Mock) -> None:
        with patch.dict("os.environ", {}, clear=False):
            legacy_logging.auto_configure()
        mock_configure.assert_called_once_with(level="INFO")

    @patch("src.candles.infrastructure.logging_config.configure_logging")
    def test_auto_configure_with_env_vars(self, mock_configure: Mock) -> None:
        with patch.dict("os.environ", {"MARKET_META_LOG_LEVEL": "DEBUG"}, clear=False):
            legacy_logging.auto_configure()
        mock_configure.assert_called_once_with(level="DEBUG")


if __name__ == "__main__":
    pytest.main([__file__])
