"""
ta_safe — PRODUCTION TA-Lib backend facade. KEEP/FREEZE (features-prune-v2 A3).

This is the LIVE production path for all indicator calculations.
Imported by: indicator_groups/ma, oscillators, squeeze, trend, volatility, volume,
             and application/feature_service.

Do NOT merge with core/normalization.py or validation/ — the parallel
normalization.py and validation.py here are intentional specialisations
(lesson from prune v1: parallelism ≠ duplication).

Universal facade for technical indicators with explicit backend chain.

Backend priority (§3.1):
    1. TA-Lib  — primary backend (fast, C-compiled)
    2. pandas_ta — compatibility layer
    3. Python fallback — rare/emergency cases only

Use safe_ta_with_status() to get explicit CalculationStatus instead of
silent NaN-masking of errors (§3.3).
"""

from __future__ import annotations

import pandas as pd

from src.logging import get_logger

from .backend import _get_available_functions, safe_ta
from .bridge import _talib_bridge
from .constants import ALLOW, get_backend
from .errors import CalculationStatus, FeatureCalcError
from .fallback import safe_ta_fallback
from .normalization import _normalize_to_df
from .validation import _validate_allowlist

logger = get_logger(__name__)

_AVAILABLE_FUNCTIONS: set[str] | None = None
_ALLOWLIST_VALIDATED = False

_EXCLUDED = frozenset({"tr", "trange", "cdl_doji", "cdl_inside", "true_range"})


def _get_available() -> set[str]:
    """Initialize allowlist and available functions lazily on first use."""
    global _ALLOWLIST_VALIDATED, _AVAILABLE_FUNCTIONS
    if not _ALLOWLIST_VALIDATED:
        _validate_allowlist(ALLOW)
        _ALLOWLIST_VALIDATED = True
    if _AVAILABLE_FUNCTIONS is None:
        _AVAILABLE_FUNCTIONS = _get_available_functions()
    return _AVAILABLE_FUNCTIONS


def safe_ta_with_fallback(
    df: pd.DataFrame, name: str, /, **kwargs: dict[str, object]
) -> pd.DataFrame:
    """
    Safe technical indicator call with explicit backend chain:
    TA-Lib → pandas_ta → Python fallback.

    Returns DataFrame (backward compatible). For explicit status tracking,
    use safe_ta_with_status() instead.
    """
    result_df, _ = safe_ta_with_status(df, name, **kwargs)
    return result_df


def safe_ta_with_status(
    df: pd.DataFrame, name: str, /, **kwargs: dict[str, object]
) -> tuple[pd.DataFrame, CalculationStatus]:
    """
    Safe technical indicator call with explicit CalculationStatus.

    Backend chain ( 3.1): TA-Lib → pandas_ta → Python fallback.
    Status ( 3.3):
        CALCULATED     — success via TA-Lib or pandas_ta (primary backends)
        FALLBACK_USED  — success via Python fallback only
        CALCULATION_FAILED — all backends failed (returns empty DataFrame)

    Args:
        df: DataFrame with OHLCV data
        name: Indicator name
        **kwargs: Indicator parameters

    Returns:
        (result_df, CalculationStatus)
    """
    if name in _EXCLUDED:
        logger.debug("Function %s excluded from pipeline", name)
        return pd.DataFrame(index=df.index), CalculationStatus.CALCULATED

    backend = get_backend()

    # 1. Try TA-Lib first (primary backend per policy)
    if backend in ("talib", "auto"):
        try:
            result = _talib_bridge(df, name, **kwargs)
            return result, CalculationStatus.CALCULATED
        except FeatureCalcError as e:
            error_text = str(e)
            if (
                "mapping not found" in error_text
                or "TA-Lib not available" in error_text
            ):
                logger.debug("TA-Lib mapping missing for %s, trying pandas_ta", name)
            else:
                if backend == "talib":
                    raise
                logger.warning("TA-Lib.%s failed: %s, trying pandas_ta", name, e)

    # 2. Try pandas_ta (compatibility layer)
    if backend in ("pandas_ta", "auto"):
        available_functions = _get_available()
        if name in available_functions:
            try:
                result = safe_ta(df, name, **kwargs)
                return result, CalculationStatus.CALCULATED
            except Exception as e:
                if backend == "pandas_ta":
                    raise FeatureCalcError(f"pandas_ta failed for {name}: {e}") from e
                logger.warning("pandas_ta.%s failed: %s, trying fallback", name, e)
        else:
            logger.debug("Function %s not available in pandas_ta", name)

    # 3. Python fallback (last resort)
    logger.warning("Using Python fallback for %s", name)
    out = safe_ta_fallback(df, name, **kwargs)
    return _normalize_to_df(out, name, df, **kwargs), CalculationStatus.FALLBACK_USED


__all__ = [
    "CalculationStatus",
    "FeatureCalcError",
    "safe_ta",
    "safe_ta_fallback",
    "safe_ta_with_fallback",
    "safe_ta_with_status",
]
