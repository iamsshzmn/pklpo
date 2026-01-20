import numpy as np
import pandas as pd
import pandas_ta as ta


def calc_squeeze_indicators(df: pd.DataFrame, available: set) -> dict:
    result = {}
    if (
        "ttm_squeeze_on" in available
        or "ttm_squeeze_hist" in available
        or "ttm_squeeze_value" in available
    ):
        try:
            squeeze = ta.squeeze_pro(df["close"], df["high"], df["low"])
            if squeeze is not None:
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
                if (
                    "ttm_squeeze_value" in available
                    and "SQZPRO_20_2.0_20_2_1.5_1" in squeeze.columns
                ):
                    result["ttm_squeeze_value"] = squeeze["SQZPRO_20_2.0_20_2_1.5_1"]

                # Обрабатываем ttm_squeeze_hist (используем то же значение, что и value)
                if (
                    "ttm_squeeze_hist" in available
                    and "SQZPRO_20_2.0_20_2_1.5_1" in squeeze.columns
                ):
                    result["ttm_squeeze_hist"] = squeeze["SQZPRO_20_2.0_20_2_1.5_1"]
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
