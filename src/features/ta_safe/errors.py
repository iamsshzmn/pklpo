"""
Exception classes and result types for ta_safe module.
"""

from __future__ import annotations

from enum import StrEnum


class FeatureCalcError(Exception):
    """Raised when indicator calculation fails."""

    pass


class CalculationStatus(StrEnum):
    """
    Explicit indicator calculation status (Stage 3.3).

    Replaces the implicit model where failures are hidden behind NaN outputs.

    Values:
        CALCULATED: Success via a primary backend such as TA-Lib or pandas_ta.
        FALLBACK_USED: Success via the Python fallback implementation.
        CALCULATION_FAILED: All available backends failed.
    """

    CALCULATED = "calculated"
    FALLBACK_USED = "fallback_used"
    CALCULATION_FAILED = "calculation_failed"
