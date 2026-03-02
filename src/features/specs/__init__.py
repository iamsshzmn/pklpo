"""
Feature specifications (declarative layer).

This package defines WHAT indicators exist: names, parameters, and metadata.
It does NOT contain calculation logic.

Boundary:
    specs/ -> declares indicator metadata (FeatureSpec dataclasses)
    indicator_groups/ -> implements calculation logic using ta_safe

Flow: specs define available indicators -> indicator_groups calculate them.
"""

from ..domain.models import FeatureSpec

# Import feature dictionaries from category modules
from .candles import CANDLES_FEATURES
from .ma import ADV_MA_FEATURES, MA_FEATURES
from .oscillators import (
    MOMENTUM_STAGE_E,
    OSC_STAGE_C,
    OSCILLATOR_FEATURES,
    STOCHRSI_FEATURES,
)
from .overlap import OVERLAP_FEATURES
from .performance import PERFORMANCE_FEATURES
from .statistics import STATISTICS_FEATURES
from .trend import TREND_FEATURES, TREND_STAGE_E
from .utils import (
    PHASE_2_REQUIRED_FEATURES,
    get_features_by_type,
    get_required_features,
    validate_phase2_requirements,
)
from .volatility import SQUEEZE_FEATURES, VOL_STAGE_D, VOLATILITY_FEATURES
from .volume import VOLM_STAGE_D, VOLUME_FEATURES

# Combine all features into FEATURE_SPECS
FEATURE_SPECS: dict[str, FeatureSpec] = {}
FEATURE_SPECS.update(TREND_FEATURES)
FEATURE_SPECS.update(TREND_STAGE_E)
FEATURE_SPECS.update(OSCILLATOR_FEATURES)
FEATURE_SPECS.update(VOLATILITY_FEATURES)
FEATURE_SPECS.update(VOLUME_FEATURES)
FEATURE_SPECS.update(MA_FEATURES)
FEATURE_SPECS.update(ADV_MA_FEATURES)
FEATURE_SPECS.update(CANDLES_FEATURES)
FEATURE_SPECS.update(SQUEEZE_FEATURES)
FEATURE_SPECS.update(STOCHRSI_FEATURES)
FEATURE_SPECS.update(OVERLAP_FEATURES)
FEATURE_SPECS.update(STATISTICS_FEATURES)
FEATURE_SPECS.update(PERFORMANCE_FEATURES)
FEATURE_SPECS.update(OSC_STAGE_C)
FEATURE_SPECS.update(VOL_STAGE_D)
FEATURE_SPECS.update(VOLM_STAGE_D)
FEATURE_SPECS.update(MOMENTUM_STAGE_E)

# Feature groups for easy access
FEATURE_GROUPS = {
    "trend": TREND_FEATURES,
    "oscillator": OSCILLATOR_FEATURES,
    "volatility": VOLATILITY_FEATURES,
    "volume": VOLUME_FEATURES,
    "ma": MA_FEATURES,
    "candles": CANDLES_FEATURES,
    "squeeze": SQUEEZE_FEATURES,
    "overlap": OVERLAP_FEATURES,
    "statistics": STATISTICS_FEATURES,
    "performance": PERFORMANCE_FEATURES,
}


# Re-export validate_feature_specs as alias for validate_phase2_requirements
# for backward compatibility with domain/indicator_specs.py
def validate_feature_specs(feature_specs: list[FeatureSpec]) -> bool:
    """
    Validate that all required features are available.

    Alias for validate_phase2_requirements for backward compatibility.

    Args:
        feature_specs: List of feature specifications

    Returns:
        True if all required features are available
    """
    return validate_phase2_requirements(feature_specs)


# Re-export public API
__all__ = [
    "FEATURE_GROUPS",
    "FEATURE_SPECS",
    "PHASE_2_REQUIRED_FEATURES",
    "FeatureSpec",
    "get_features_by_type",
    "get_required_features",
    "validate_feature_specs",
    "validate_phase2_requirements",
]
