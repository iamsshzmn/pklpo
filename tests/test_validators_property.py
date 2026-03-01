"""Property-based tests for validation contracts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings, strategies as st

from src.features.validation.data_validator import DataValidator
from src.features.validation.gate_validator import GateValidator


@st.composite
def _valid_ohlcv_df(draw: st.DrawFn) -> pd.DataFrame:
    size = draw(st.integers(min_value=1, max_value=200))
    close = draw(
        st.lists(
            st.floats(
                min_value=0.01,
                max_value=1_000_000,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=size,
            max_size=size,
        )
    )
    open_ = draw(
        st.lists(
            st.floats(
                min_value=0.01,
                max_value=1_000_000,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=size,
            max_size=size,
        )
    )
    high_delta = draw(
        st.lists(
            st.floats(
                min_value=0.0,
                max_value=100.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=size,
            max_size=size,
        )
    )
    low_delta = draw(
        st.lists(
            st.floats(
                min_value=0.0,
                max_value=100.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=size,
            max_size=size,
        )
    )
    volume = draw(
        st.lists(
            st.floats(
                min_value=0.0,
                max_value=1_000_000_000,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=size,
            max_size=size,
        )
    )

    close_arr = np.array(close, dtype=float)
    open_arr = np.array(open_, dtype=float)
    high_arr = np.maximum(open_arr, close_arr) + np.array(high_delta, dtype=float)
    low_arr = np.minimum(open_arr, close_arr) - np.array(low_delta, dtype=float)
    low_arr = np.maximum(low_arr, 0.0)
    high_arr = np.maximum(high_arr, low_arr)

    ts_start = draw(st.integers(min_value=1_600_000_000, max_value=1_900_000_000))
    ts = [ts_start + i * 60 for i in range(size)]

    return pd.DataFrame(
        {
            "open": open_arr,
            "high": high_arr,
            "low": low_arr,
            "close": close_arr,
            "volume": np.array(volume, dtype=float),
            "ts": ts,
        }
    )


@settings(max_examples=100)
@given(df=_valid_ohlcv_df())
def test_valid_ohlcv_dataframe_passes_data_validator(df: pd.DataFrame) -> None:
    validator = DataValidator()
    result = validator.validate_ohlcv_data(df)
    assert result["valid"] is True


@settings(max_examples=100)
@given(df=_valid_ohlcv_df())
def test_negative_prices_and_nan_timestamps_are_rejected(df: pd.DataFrame) -> None:
    validator = DataValidator()

    bad_price_df = df.copy()
    bad_price_df.loc[0, "open"] = -1.0
    price_result = validator.validate_ohlcv_data(bad_price_df)
    assert price_result["valid"] is False

    bad_ts_df = df.copy()
    bad_ts_df.loc[0, "ts"] = np.nan
    ts_result = validator.validate_ohlcv_data(bad_ts_df)
    assert ts_result["valid"] is False


@settings(max_examples=100)
@given(
    values=st.lists(
        st.one_of(st.none(), st.floats(allow_nan=False, allow_infinity=False)),
        min_size=1,
        max_size=200,
    )
)
def test_gate_fill_rate_is_always_between_zero_and_one(
    values: list[float | None],
) -> None:
    df = pd.DataFrame(
        {
            "open": [100.0] * len(values),
            "high": [101.0] * len(values),
            "low": [99.0] * len(values),
            "close": [100.0] * len(values),
            "volume": [1000.0] * len(values),
            "ema_8": values,
        }
    )
    quality = GateValidator()._calculate_overall_quality(df)
    fill_rate = quality["fill_rate"]
    assert 0.0 <= fill_rate <= 1.0
