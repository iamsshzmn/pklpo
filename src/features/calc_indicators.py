"""Backward-compatible facade for legacy calc_indicators imports."""

from .core import compute_features, get_available_features, get_feature_info

calc_indicators = compute_features

__all__ = [
    "calc_indicators",
    "compute_features",
    "get_available_features",
    "get_feature_info",
]
