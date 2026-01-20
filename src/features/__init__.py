"""
Features module for memory-optimized indicator calculations.
"""

try:
    # Import-heavy; make optional to allow importing lightweight submodules (e.g., validators)
    from .core import compute_features  # type: ignore
except Exception:  # pragma: no cover - optional at import time

    def compute_features(*args, **kwargs):  # type: ignore
        raise ImportError(
            "features.core dependencies are not available. Install runtime deps or import 'features.core' directly."
        )


from .specs import FEATURE_SPECS, FeatureSpec
from .traceability import (
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
    "compute_features",
    "FEATURE_SPECS",
    "FeatureSpec",
    "FeatureTracer",
    "FeatureMetadata",
    "get_global_tracer",
    "enable_tracing",
    "disable_tracing",
    "track_feature",
    "get_feature_metadata",
]
