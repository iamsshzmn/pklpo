"""
Core feature calculation module.

This package provides the main interface for calculating technical indicators
with online/offline parity and group-based architecture.

Public API:
    - compute_features: Main function for calculating features
    - compute_features_new: New unified interface with group-based calculation
    - get_available_features: List all available feature names
    - get_feature_info: Get information about a specific feature
    - validate_feature_compatibility: Validate OHLCV data compatibility
"""

# Import public API functions
from .calculation import compute_features, compute_features_new
from .utils import get_available_features, get_feature_info
from .validation import validate_feature_compatibility

# Re-export for backward compatibility
__all__ = [
    "compute_features",
    "compute_features_new",
    "get_available_features",
    "get_feature_info",
    "validate_feature_compatibility",
]
