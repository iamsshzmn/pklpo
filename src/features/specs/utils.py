"""
Utility functions for feature specifications.

This module provides helper functions for querying and validating feature specifications.
"""

from ..models import FeatureSpec

# Required features for Phase 2 (as specified in the plan)
PHASE_2_REQUIRED_FEATURES = [
    "atr_14",  # ATR
    "rsi_14",  # RSI
    "ema_12",  # EMA
    "ema_26",  # EMA
    "macd",  # MACD
    "macd_signal",  # MACD Signal
    "macd_histogram",  # MACD Histogram
    "obv",  # OBV
    "parkinson_vol",  # Parkinson Volatility
    "vwap",  # Rolling VWAP
]


def get_features_by_type(feature_type: str) -> dict[str, FeatureSpec]:
    """
    Get all features of a specific type.

    Args:
        feature_type: Type of features to return

    Returns:
        Dictionary of feature specifications
    """
    # Import FEATURE_GROUPS from __init__.py using lazy import to avoid circular dependency
    # The __init__.py will define FEATURE_GROUPS after importing this module
    import sys

    # Get FEATURE_GROUPS from the parent __init__.py module (lazy import)
    parent_module = sys.modules.get("src.features.specs")
    if parent_module and hasattr(parent_module, "FEATURE_GROUPS"):
        groups = parent_module.FEATURE_GROUPS
        if isinstance(groups, dict):
            result = groups.get(feature_type, {})
            # Type check to ensure result is dict[str, FeatureSpec]
            if isinstance(result, dict):
                return result
    # Fallback: return empty dict if FEATURE_GROUPS not yet initialized
    return {}


def get_required_features() -> list[str]:
    """
    Get list of features required for Phase 2.

    Returns:
        List of required feature names
    """
    return PHASE_2_REQUIRED_FEATURES


def validate_phase2_requirements(feature_specs: list[FeatureSpec]) -> bool:
    """
    Validate that all required features for Phase 2 are available.

    Args:
        feature_specs: List of feature specifications

    Returns:
        True if all required features are available

    Raises:
        ValueError: If required features are missing
    """
    available_features = {spec.name for spec in feature_specs}
    required_features = set(PHASE_2_REQUIRED_FEATURES)

    missing_features = required_features - available_features
    if missing_features:
        raise ValueError(f"Missing required features: {missing_features}")

    return True
