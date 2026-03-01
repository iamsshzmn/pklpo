"""
Utility functions for feature management.

This module provides helper functions for querying feature information
and listing available features.
"""

from ..specs import FEATURE_SPECS, FeatureSpec


def get_available_features() -> list[str]:
    """
    Get list of all available feature names.

    Returns:
        List of feature names

    Example:
        >>> features = get_available_features()
        >>> 'rsi_14' in features
        True
    """
    return list(FEATURE_SPECS.keys())


def get_feature_info(feature_name: str) -> FeatureSpec | None:
    """
    Get information about a specific feature.

    Args:
        feature_name: Name of the feature (e.g., 'rsi_14', 'sma_20')

    Returns:
        FeatureSpec object with feature metadata, or None if feature not found

    Example:
        >>> spec = get_feature_info('rsi_14')
        >>> spec.name if spec else None
        'rsi_14'
        >>> get_feature_info('nonexistent')
        None
    """
    return FEATURE_SPECS.get(feature_name)
