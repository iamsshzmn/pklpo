"""Backward-compatible logging facade for features."""

from src.logging import (
    get_features_logger,
    log_batch_metrics,
    log_feature_quality,
    performance_timer,
    setup_features_logging,
)

__all__ = [
    "get_features_logger",
    "log_batch_metrics",
    "log_feature_quality",
    "performance_timer",
    "setup_features_logging",
]
