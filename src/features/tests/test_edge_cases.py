import numpy as np
import pandas as pd
import pytest

from ..core import compute_features
from ..validators import validate_ohlcv_data


def make_ohlcv(n: int = 10, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.Series(np.arange(n) * 60, name="ts")
    close = pd.Series(100 + rng.normal(0, 1, n).cumsum(), name="close")
    open_ = pd.Series(close.shift(1).fillna(close.iloc[0]), name="open")
    high = pd.concat([open_, close], axis=1).max(axis=1) + np.abs(rng.normal(0, 0.5, n))
    low = pd.concat([open_, close], axis=1).min(axis=1) - np.abs(rng.normal(0, 0.5, n))
    volume = pd.Series(rng.integers(1000, 5000, n), name="volume")
    return pd.concat(
        [ts, open_, high.rename("high"), low.rename("low"), close, volume], axis=1
    )


class TestEdgeCases:
    def test_short_series(self):
        # Меньше окна индикаторов (например, RSI(14))
        df = make_ohlcv(n=8)
        validate_ohlcv_data(df)

        features = compute_features(
            df, specs=["rsi_14", "atr_14"], volatility_normalize=False
        )

        # Должен вернуть корректный DataFrame той же длины
        assert isinstance(features, pd.DataFrame)
        assert len(features) == len(df)
        # Значения могут быть NaN, но без исключений и со столбцами
        assert "rsi_14" in features.columns
        assert "atr_14" in features.columns

    def test_missing_values_handling(self):
        df = make_ohlcv(n=50)
        # Вставим пропуски в цену и объём
        df.loc[5:7, "close"] = np.nan
        df.loc[10, "volume"] = np.nan

        validate_ohlcv_data(
            df
        )  # базовая валидация пропускает NaN, но проверяет отношения

        features = compute_features(
            df, specs=["rsi_14", "obv"], volatility_normalize=False
        )
        assert len(features) == len(df)
        # Допускаем NaN, но столбцы существуют
        assert "rsi_14" in features
        assert "obv" in features

    def test_non_monotonic_timestamps(self):
        df = make_ohlcv(n=30)
        # Нарушим порядок временных меток
        df.loc[10, "ts"], df.loc[11, "ts"] = df.loc[11, "ts"], df.loc[10, "ts"]

        # Базовая валидация должна поднять предупреждение/ошибку при последующих шагах
        # compute_features должен либо упасть, либо отсигналить о проблеме через исключение
        with pytest.raises(Exception):
            compute_features(df, specs=["rsi_14"], volatility_normalize=False)
