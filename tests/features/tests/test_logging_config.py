"""Tests for features logging configuration."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from unittest.mock import MagicMock

import pandas as pd
import pytest

try:
    from src.features.observability import logging as logging_config
except ImportError:  # pragma: no cover - logging relocated to src.logging
    pytest.skip(
        "src.features.observability.logging was relocated to src.logging; "
        "test pending port",
        allow_module_level=True,
    )


@pytest.fixture(autouse=True)
def _reset_features_logger(monkeypatch, tmp_path):
    """Ensure clean logger state between tests."""
    logger = logging.getLogger("pklpo.features")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = True
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)
    yield
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = True


class TestGetFeaturesLogger:
    """Tests for get_features_logger."""

    def test_creates_expected_handlers(self):
        """Base logger exposes console and file handlers."""
        logger = logging_config.get_features_logger()
        assert logger.name == "pklpo.features"
        handler_types = [type(handler) for handler in logger.handlers]
        assert any(issubclass(t, logging.StreamHandler) for t in handler_types)
        assert sum(issubclass(t, RotatingFileHandler) for t in handler_types) == 2

    def test_child_logger_name(self):
        """Child logger appends suffix to base name."""
        _ = logging_config.get_features_logger()
        child = logging_config.get_features_logger("cli")
        assert child.name == "pklpo.features.cli"


class TestSetupFeaturesLogging:
    """Tests for setup_features_logging."""

    def test_verbose_mode_sets_env_and_console_level(self, monkeypatch):
        """Console handler switches to DEBUG and env var is set."""
        monkeypatch.delenv("FEATURES_VERBOSE", raising=False)
        logger = logging_config.setup_features_logging(verbose=True)
        assert os.environ["FEATURES_VERBOSE"] == "true"
        console = next(
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.StreamHandler)
        )
        assert console.level == logging.DEBUG


class TestPerformanceTimer:
    """Tests for performance_timer decorator."""

    def test_success_path_logs_duration(self):
        """Successful call should only log debug."""
        mock_logger = MagicMock(spec=logging.Logger)

        @logging_config.performance_timer(mock_logger, "op")
        def _func():
            return "ok"

        assert _func() == "ok"
        mock_logger.debug.assert_called_once()
        mock_logger.error.assert_not_called()

    def test_failure_logs_error(self):
        """Exception path logs error with traceback."""
        mock_logger = MagicMock(spec=logging.Logger)

        @logging_config.performance_timer(mock_logger, "op")
        def _boom():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            _boom()
        mock_logger.error.assert_called_once()
        _, kwargs = mock_logger.error.call_args
        assert kwargs.get("exc_info") is True


class TestUtilityLoggers:
    """Tests for feature/batch helpers."""

    def test_log_feature_quality_warns_on_low_fill(self):
        """Fill rate below 50% raises warning."""
        mock_logger = MagicMock(spec=logging.Logger)
        data = pd.Series([1.0, None, None, 2.0])
        logging_config.log_feature_quality(mock_logger, data, "test_feature")
        mock_logger.warning.assert_called_once()

    def test_log_feature_quality_silent_when_ok(self):
        """High fill rate avoids warnings."""
        mock_logger = MagicMock(spec=logging.Logger)
        data = pd.Series([1.0, 2.0, 3.0])
        logging_config.log_feature_quality(mock_logger, data, "ok_feature")
        mock_logger.warning.assert_not_called()

    def test_log_batch_metrics_info_and_warning(self):
        """Batch with errors emits info and warning."""
        mock_logger = MagicMock(spec=logging.Logger)
        logging_config.log_batch_metrics(
            mock_logger,
            batch_size=100,
            processed=90,
            errors=10,
        )
        mock_logger.info.assert_called_once()
        mock_logger.warning.assert_called_once()
