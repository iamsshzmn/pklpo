import numpy as np
import pandas as pd
import pandas_ta as ta


def calc_volume_indicators(df: pd.DataFrame, available: set) -> dict:
    result = {}

    # Конвертируем числовые колонки в float
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # OBV
    if "obv" in available:
        obv_series = ta.obv(df["close"], df["volume"])
        result["obv"] = (
            obv_series
            if obv_series is not None
            else pd.Series([np.nan] * len(df), index=df.index)
        )
    # CMF
    if "cmf" in available:
        cmf_series = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=20)
        result["cmf"] = (
            cmf_series
            if cmf_series is not None
            else pd.Series([np.nan] * len(df), index=df.index)
        )
    # VWAP - упрощенная версия
    if "vwap" in available:
        try:
            # Простой VWAP без индекса времени
            typical_price = (df["high"] + df["low"] + df["close"]) / 3
            vwap_series = (typical_price * df["volume"]).cumsum() / df[
                "volume"
            ].cumsum()
            result["vwap"] = vwap_series
        except Exception as e:
            print(f"❌ Ошибка VWAP: {e}")
            result["vwap"] = pd.Series([np.nan] * len(df), index=df.index)

    # Volume SMA
    if "volume_sma20" in available:
        volume_sma_series = ta.sma(df["volume"], length=20)
        result["volume_sma20"] = (
            volume_sma_series
            if volume_sma_series is not None
            else pd.Series([np.nan] * len(df), index=df.index)
        )

    # Volume Profile - упрощенная версия
    if any(
        indicator in available
        for indicator in [
            "vp_point_of_control",
            "vp_value_area_high",
            "vp_value_area_low",
        ]
    ):
        try:
            # Простая реализация Volume Profile
            window_size = min(50, len(df))

            vp_poc = pd.Series([np.nan] * len(df), index=df.index)
            vp_vah = pd.Series([np.nan] * len(df), index=df.index)
            vp_val = pd.Series([np.nan] * len(df), index=df.index)

            for i in range(window_size, len(df)):
                window_df = df.iloc[i - window_size : i + 1]

                # Рассчитываем Volume Profile для окна
                price = window_df["close"]
                volume = window_df["volume"]

                if len(price) > 10:  # Минимум 10 точек
                    bins = min(20, len(price) // 2)
                    hist, bin_edges = np.histogram(price, bins=bins, weights=volume)

                    if hist.sum() > 0:
                        poc_idx = np.argmax(hist)
                        poc = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2

                        total_volume = hist.sum()
                        sorted_idx = np.argsort(hist)[::-1]
                        cumsum = 0
                        value_area_bins = []

                        for idx in sorted_idx:
                            cumsum += hist[idx]
                            value_area_bins.append(idx)
                            if cumsum >= 0.7 * total_volume:
                                break

                        if value_area_bins:
                            vah = max([bin_edges[i + 1] for i in value_area_bins])
                            val = min([bin_edges[i] for i in value_area_bins])

                            vp_poc.iloc[i] = poc
                            vp_vah.iloc[i] = vah
                            vp_val.iloc[i] = val

            if "vp_point_of_control" in available:
                result["vp_point_of_control"] = vp_poc
            if "vp_value_area_high" in available:
                result["vp_value_area_high"] = vp_vah
            if "vp_value_area_low" in available:
                result["vp_value_area_low"] = vp_val

        except Exception as e:
            print(f"❌ Ошибка Volume Profile: {e}")
            # Заполняем NaN для всех Volume Profile индикаторов
            for indicator in [
                "vp_point_of_control",
                "vp_value_area_high",
                "vp_value_area_low",
            ]:
                if indicator in available:
                    result[indicator] = pd.Series([np.nan] * len(df), index=df.index)

    return result
