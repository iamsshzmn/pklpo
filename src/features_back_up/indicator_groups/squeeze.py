import numpy as np
import pandas as pd

from src.logging import get_logger

from ..ta_safe import safe_ta_with_fallback
from ..utils.indicator_utils import check_min_length

logger = get_logger(__name__)


def calc_squeeze_indicators(df: pd.DataFrame, available: set) -> dict:
    result = {}
    if (
        "ttm_squeeze_on" in available
        or "ttm_squeeze_hist" in available
        or "ttm_squeeze_value" in available
    ):
        try:
            if not check_min_length(df, "ttm_squeeze"):
                logger.warning(
                    "TTM SQUEEZE: недостаточно данных (len<20), возвращаю NaN"
                )
                squeeze = None
            else:
                squeeze = safe_ta_with_fallback(df, "squeeze_pro")
            if squeeze is not None and isinstance(squeeze, pd.DataFrame):
                # Маппинг колонок pandas_ta на наши названия

                # Обрабатываем ttm_squeeze_on
                if "ttm_squeeze_on" in available:
                    if (
                        "SQZPRO_ON_WIDE" in squeeze.columns
                        or "SQZPRO_ON_NORMAL" in squeeze.columns
                        or "SQZPRO_ON_NARROW" in squeeze.columns
                    ):
                        on_wide = squeeze.get(
                            "SQZPRO_ON_WIDE", pd.Series([0] * len(squeeze))
                        )
                        on_normal = squeeze.get(
                            "SQZPRO_ON_NORMAL", pd.Series([0] * len(squeeze))
                        )
                        on_narrow = squeeze.get(
                            "SQZPRO_ON_NARROW", pd.Series([0] * len(squeeze))
                        )
                        result["ttm_squeeze_on"] = (
                            (on_wide + on_normal + on_narrow) > 0
                        ).astype(int)
                    else:
                        result["ttm_squeeze_on"] = pd.Series(
                            [np.nan] * len(df), index=df.index
                        )

                # Обрабатываем ttm_squeeze_value
                if "ttm_squeeze_value" in available:
                    # Find the SQZPRO value column (first column with SQZPRO_ pattern)
                    value_col = next(
                        (
                            c
                            for c in squeeze.columns
                            if c.startswith("SQZPRO_")
                            and not c.endswith("_ON_")
                            and not c.endswith("_OFF")
                            and not c.endswith("_NO")
                        ),
                        None,
                    )
                    if value_col is not None:
                        result["ttm_squeeze_value"] = squeeze[value_col]
                    else:
                        result["ttm_squeeze_value"] = pd.Series(
                            [np.nan] * len(df), index=df.index
                        )

                # Обрабатываем ttm_squeeze_hist (используем то же значение, что и value)
                if "ttm_squeeze_hist" in available:
                    # Find the SQZPRO value column (first column with SQZPRO_ pattern)
                    value_col = next(
                        (
                            c
                            for c in squeeze.columns
                            if c.startswith("SQZPRO_")
                            and not c.endswith("_ON_")
                            and not c.endswith("_OFF")
                            and not c.endswith("_NO")
                        ),
                        None,
                    )
                    if value_col is not None:
                        result["ttm_squeeze_hist"] = squeeze[value_col]
                    else:
                        result["ttm_squeeze_hist"] = pd.Series(
                            [np.nan] * len(df), index=df.index
                        )
            else:
                if "ttm_squeeze_on" in available:
                    result["ttm_squeeze_on"] = pd.Series(
                        [np.nan] * len(df), index=df.index
                    )
                if "ttm_squeeze_hist" in available:
                    result["ttm_squeeze_hist"] = pd.Series(
                        [np.nan] * len(df), index=df.index
                    )
                if "ttm_squeeze_value" in available:
                    result["ttm_squeeze_value"] = pd.Series(
                        [np.nan] * len(df), index=df.index
                    )
        except Exception as e:
            print(f"Ошибка в calc_squeeze_indicators: {e}")
            if "ttm_squeeze_on" in available:
                result["ttm_squeeze_on"] = pd.Series([np.nan] * len(df), index=df.index)
            if "ttm_squeeze_hist" in available:
                result["ttm_squeeze_hist"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )
            if "ttm_squeeze_value" in available:
                result["ttm_squeeze_value"] = pd.Series(
                    [np.nan] * len(df), index=df.index
                )
    return result
