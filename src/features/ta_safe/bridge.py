"""
TA-Lib bridge for technical indicators via adapter dispatch table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .adapters import TALIB_DISPATCH
from .errors import FeatureCalcError

if TYPE_CHECKING:
    import pandas as pd


def _talib_bridge(
    df: pd.DataFrame, name: str, **kwargs: dict[str, object]
) -> pd.DataFrame:
    """
    Dispatch indicator call to TA-Lib adapter.

    TTM Squeeze (`squeeze`, `squeeze_pro`) is intentionally not mapped:
    there is no TA-Lib equivalent and it remains custom implementation.
    """
    adapter = TALIB_DISPATCH.get(name)
    if adapter is None:
        raise FeatureCalcError(f"TA-Lib mapping not found for {name}")

    try:
        return adapter(df, **kwargs)
    except ImportError as err:
        raise FeatureCalcError("TA-Lib not available") from err
    except Exception as err:
        raise FeatureCalcError(f"TA-Lib failed for {name}: {err}") from err
