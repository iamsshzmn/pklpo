import numpy as np
import pandas as pd
import pandas_ta as ta


def calc_trend_indicators(df, available: set[str]):
    result = {}

    # === Ichimoku Cloud ===
    if any(key.startswith("ichimoku") for key in available):
        ichimoku_df = ta.ichimoku(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            tenkan=9,
            kijun=26,
            senkou=52,
        )

        if ichimoku_df is None:
            # Убираем логи - они не нужны в терминале
            for key in [
                "ichimoku_tenkan",
                "ichimoku_kijun",
                "ichimoku_senkou_a",
                "ichimoku_senkou_b",
                "ichimoku_chikou",
            ]:
                if key in available:
                    result[key] = pd.Series([np.nan] * len(df), index=df.index)
        else:
            # Если вернулся tuple/list, берём первый элемент
            if isinstance(ichimoku_df, list | tuple):
                ichimoku_df = ichimoku_df[0]
                # Убираем логи - они не нужны в терминале

            if isinstance(ichimoku_df, pd.DataFrame):
                # Убираем логи - они не нужны в терминале
                if "ichimoku_tenkan" in available and "ITS_9" in ichimoku_df.columns:
                    result["ichimoku_tenkan"] = ichimoku_df["ITS_9"]
                if "ichimoku_kijun" in available and "IKS_26" in ichimoku_df.columns:
                    result["ichimoku_kijun"] = ichimoku_df["IKS_26"]
                if "ichimoku_senkou_a" in available and "ISA_9" in ichimoku_df.columns:
                    result["ichimoku_senkou_a"] = ichimoku_df["ISA_9"]
                if "ichimoku_senkou_b" in available and "ISB_26" in ichimoku_df.columns:
                    result["ichimoku_senkou_b"] = ichimoku_df["ISB_26"]
                if "ichimoku_chikou" in available and "ICS_26" in ichimoku_df.columns:
                    # Chikou Span имеет сдвиг назад, последние строки всегда nan
                    # Заменяем NaN на 0 (валидное числовое значение)
                    chikou_values = ichimoku_df["ICS_26"].fillna(0)
                    result["ichimoku_chikou"] = chikou_values
            else:
                # Убираем логи - они не нужны в терминале
                pass

    # === ADX ===
    if any(key.startswith("adx") for key in available):
        adx_df = ta.adx(high=df["high"], low=df["low"], close=df["close"], length=14)

        if adx_df is not None:
            if "adx14" in available and "ADX_14" in adx_df.columns:
                result["adx14"] = adx_df["ADX_14"]
            if "adx_pos_di" in available and "DMP_14" in adx_df.columns:
                result["adx_pos_di"] = adx_df["DMP_14"]
            if "adx_neg_di" in available and "DMN_14" in adx_df.columns:
                result["adx_neg_di"] = adx_df["DMN_14"]
        else:
            for key in ["adx14", "adx_pos_di", "adx_neg_di"]:
                if key in available:
                    result[key] = pd.Series([np.nan] * len(df), index=df.index)

    return result
