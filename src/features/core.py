"""
Core module for feature calculation with online/offline parity.

This module provides a unified interface for calculating technical features
without look-ahead bias, ensuring consistent results between online and offline modes.

NOTE: This module is now a compatibility shim. The actual implementation
has been moved to the `core/` package. This file re-exports the public API
for backward compatibility.
"""

# Re-export all public API from the new core package
from .core import (
    compute_features,
    compute_features_new,
    get_available_features,
    get_feature_info,
    validate_feature_compatibility,
)

__all__ = [
    "compute_features",
    "compute_features_new",
    "get_available_features",
    "get_feature_info",
    "validate_feature_compatibility",
]
