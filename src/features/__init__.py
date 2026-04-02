"""
Features module for memory-optimized indicator calculations.
"""

from .api import (
    FEATURE_SPECS,
    FeatureApplicationBootstrap,
    FeatureResult,
    FeatureSpec,
    IndicatorStorageContract,
    compute_features,
    create_feature_application_bootstrap,
)
from .observability.traceability import (
    FeatureMetadata,
    FeatureTracer,
    disable_tracing,
    enable_tracing,
    get_feature_metadata,
    get_global_tracer,
    track_feature,
)

__version__ = "1.0.0"
__author__ = "Memory Optimization Team"

__all__ = [
    "FEATURE_SPECS",
    "FeatureApplicationBootstrap",
    "FeatureMetadata",
    "FeatureResult",
    "FeatureSpec",
    "FeatureTracer",
    "IndicatorStorageContract",
    "compute_features",
    "create_feature_application_bootstrap",
    "disable_tracing",
    "enable_tracing",
    "get_feature_metadata",
    "get_global_tracer",
    "track_feature",
]
