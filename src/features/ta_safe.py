"""
Универсальный фасад для pandas_ta с жесткими проверками.

This module serves as a compatibility layer, re-exporting functions
from the refactored `src.features.ta_safe` package.
"""

# Re-export public API from the new ta_safe package for backward compatibility
from .ta_safe import (
    FeatureCalcError,
    safe_ta,
    safe_ta_fallback,
    safe_ta_with_fallback,
)

__all__ = [
    "FeatureCalcError",
    "safe_ta",
    "safe_ta_fallback",
    "safe_ta_with_fallback",
]
