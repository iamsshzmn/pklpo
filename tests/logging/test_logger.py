from __future__ import annotations

import logging

from src.logging import logger as logger_module


def test_get_logger_falls_back_to_console_when_file_handler_fails(
    monkeypatch,
    caplog,
) -> None:
    base_logger = logging.getLogger("pklpo")
    original_handlers = list(base_logger.handlers)
    original_filters = list(base_logger.filters)
    original_propagate = base_logger.propagate
    original_base_logger = logger_module._base_logger

    def fail_file_handler(*args, **kwargs):
        raise PermissionError("cannot write test log file")

    try:
        base_logger.handlers.clear()
        base_logger.filters.clear()
        logger_module._base_logger = None
        monkeypatch.setattr(logger_module, "_build_file_handler", fail_file_handler)

        with caplog.at_level(logging.WARNING):
            log = logger_module.get_logger("probe")

        assert log.name == "pklpo.probe"
        assert len(base_logger.handlers) == 1
        assert isinstance(base_logger.handlers[0], logging.StreamHandler)
        assert "file logging disabled" in caplog.text
    finally:
        base_logger.handlers.clear()
        base_logger.handlers.extend(original_handlers)
        base_logger.filters.clear()
        base_logger.filters.extend(original_filters)
        base_logger.propagate = original_propagate
        logger_module._base_logger = original_base_logger
