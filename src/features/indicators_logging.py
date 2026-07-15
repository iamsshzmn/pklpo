"""Backward-compatible indicator logging helpers."""

from src.logging import get_features_logger


def log_indicator_calculation(indicator: str, **kwargs: object) -> None:
    get_features_logger("features.indicators").info(
        "indicator=%s payload=%s", indicator, kwargs
    )


__all__ = ["get_features_logger", "log_indicator_calculation"]
