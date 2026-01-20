"""
Feature presets module.

Provides predefined sets of indicators for common use cases.
"""

from .features_calc_short_v1 import (
    CONTEXT_FEATURES,
    FEATURES_CALC_SHORT_SPECS,
    TRIGGER_FEATURES,
)

__all__ = ["FEATURES_CALC_SHORT_SPECS", "CONTEXT_FEATURES", "TRIGGER_FEATURES"]
