"""
Universal facade for pandas_ta with strict validation and fallback chain.
"""

from __future__ import annotations

import pandas as pd

from src.logging import get_logger

from .backend import _get_available_functions, safe_ta
from .bridge import _talib_bridge
from .constants import ALLOW, BACKEND
from .errors import FeatureCalcError
from .fallback import safe_ta_fallback
from .normalization import _normalize_to_df
from .validation import _validate_allowlist

logger = get_logger(__name__)

_AVAILABLE_FUNCTIONS: set[str] | None = None
_ALLOWLIST_VALIDATED = False


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
    Safe technical indicator call with backend chain:
    pandas_ta -> TA-Lib -> Python fallback.
    """
    excluded = {"tr", "trange", "cdl_doji", "cdl_inside", "true_range"}
    if name in excluded:
        logger.debug("Function %s excluded from pipeline", name)
        return pd.DataFrame(index=df.index)

    if BACKEND in ("pandas_ta", "auto"):
        available_functions = _get_available()
        if name in available_functions:
            try:
                return safe_ta(df, name, **kwargs)
            except Exception as e:
                if BACKEND == "pandas_ta":
                    raise FeatureCalcError(f"pandas_ta failed for {name}: {e}") from e
                logger.warning("pandas_ta.%s failed: %s, trying TA-Lib/fallback", name, e)
        elif BACKEND == "pandas_ta":
            logger.warning("Function %s not available in pandas_ta, using fallback", name)
            out = safe_ta_fallback(df, name, **kwargs)
            return _normalize_to_df(out, name, df, **kwargs)
        else:
            logger.debug(
                "Function %s not available in pandas_ta, trying TA-Lib/fallback", name
            )

    if BACKEND in ("talib", "auto"):
        try:
            return _talib_bridge(df, name, **kwargs)
        except Exception as e:
            error_text = str(e)
            # Not every indicator has a TA-Lib equivalent; keep pipeline robust.
            if "mapping not found" in error_text:
                logger.warning("TA-Lib mapping missing for %s, using fallback", name)
                out = safe_ta_fallback(df, name, **kwargs)
                return _normalize_to_df(out, name, df, **kwargs)
            if BACKEND == "talib":
                raise FeatureCalcError(f"TA-Lib failed for {name}: {e}") from e
            logger.warning("TA-Lib.%s failed: %s, trying fallback", name, e)

    logger.warning("Using fallback for %s", name)
    out = safe_ta_fallback(df, name, **kwargs)
    return _normalize_to_df(out, name, df, **kwargs)


__all__ = [
    "FeatureCalcError",
    "safe_ta",
    "safe_ta_fallback",
    "safe_ta_with_fallback",
]
