"""
Shim module for backward compatibility with indicator_utils.

This module redirects to the canonical indicator_utils in utils/ package.
"""

import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .utils.indicator_utils import *  # noqa: F403

# Re-export from canonical module
import pandas as pd

from .core import compute_features
from .utils.indicator_utils import *  # noqa: F403


def calc_indicators(df: pd.DataFrame, available: set[str]) -> pd.DataFrame:
    """
    DEPRECATED: Use compute_features() instead.

    Универсальный расчет всех индикаторов по группам.
    This function is kept for backward compatibility.
    """
    warnings.warn(
        "calc_indicators() is deprecated. Use compute_features() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Use the new unified interface
    return compute_features(
        df_ohlcv=df,
        available=available,
        volatility_normalize=False,  # Keep original behavior
    )
