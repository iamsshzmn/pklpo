"""
Feature specifications for the features module.

This module serves as a compatibility layer, re-exporting functions
from the refactored `src.features.specs` package.
"""

# Re-export public API from the new specs package for backward compatibility
from .specs import (
    FEATURE_GROUPS,
    FEATURE_SPECS,
    PHASE_2_REQUIRED_FEATURES,
    FeatureSpec,
    get_features_by_type,
    get_required_features,
    validate_feature_specs,
    validate_phase2_requirements,
)

__all__ = [
    "FEATURE_SPECS",
    "FEATURE_GROUPS",
    "PHASE_2_REQUIRED_FEATURES",
    "FeatureSpec",
    "get_features_by_type",
    "get_required_features",
    "validate_phase2_requirements",
    "validate_feature_specs",
]
