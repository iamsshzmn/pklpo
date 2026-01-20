import pandas as pd

from .indicator_groups import (
    calc_ma_indicators,
    calc_oscillator_indicators,
    calc_squeeze_indicators,
    calc_trend_indicators,
    calc_volatility_indicators,
    calc_volume_indicators,
)


def calc_indicators(df: pd.DataFrame, available: set) -> pd.DataFrame:
    """
    Универсальный расчет всех индикаторов по группам.
    """
    result = {}
    result.update(calc_ma_indicators(df, available))
    result.update(calc_oscillator_indicators(df, available))
    result.update(calc_volatility_indicators(df, available))
    result.update(calc_volume_indicators(df, available))
    result.update(calc_trend_indicators(df, available))
    result.update(calc_squeeze_indicators(df, available))

    # Создаем DataFrame с индексом исходного df
    result_df = pd.DataFrame(index=df.index)

    # Добавляем OHLCV данные (нужны для правил сигналов)
    ohlcv_columns = ["open", "high", "low", "close", "volume"]
    for col in ohlcv_columns:
        if col in df.columns:
            result_df[col] = df[col].values

    # Добавляем все индикаторы как столбцы с одинаковыми значениями
    for key, value in result.items():
        result_df[key] = value

    # Теперь гарантируем наличие столбца 'ts' первым
    if "ts" not in result_df.columns:
        if "ts" in df.columns:
            result_df.insert(0, "ts", df["ts"].values)
        else:
            if isinstance(df.index, pd.DatetimeIndex):
                result_df.insert(0, "ts", df.index)
            else:
                result_df.insert(0, "ts", df.index.astype("int64"))
    # Нормализуем ts к int-секундам Unix-эпохи (как в модели Indicator)
    ts_col = result_df["ts"]
    if pd.api.types.is_datetime64_any_dtype(ts_col):
        result_df["ts"] = (ts_col.astype("int64") // 10**9).astype("int64")
    else:
        # Если ts уже в миллисекундах, конвертируем в секунды
        if ts_col.max() > 1e12:  # Если больше 1e12, то это миллисекунды
            result_df["ts"] = (ts_col.astype("int64") // 1000).astype("int64")
        else:
            result_df["ts"] = ts_col.astype("int64")
    return result_df
