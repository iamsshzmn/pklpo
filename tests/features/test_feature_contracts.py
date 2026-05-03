import numpy as np
import pandas as pd
import pytest

from src.features.api import compute_features
from src.features.core.group_calculation import CALCULATION_ORDER
from src.features.core.group_calculator import GroupFeatureCalculator

WARMUP = 250
GROUP_FEATURES = {
    "overlap": {"hl2"},
    "ma": {"ema_21"},
    "oscillators": {"rsi_14"},
    "volatility": {"atr_14"},
    "volume": {"obv"},
    "trend": {"adx_14"},
    "candles": {"ha_close"},
    "squeeze": {"ttm_squeeze_hist"},
    "statistics": {"zscore_20"},
    "performance": {"log_return"},
}


def _make_ohlcv(rows: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.5, rows))
    open_ = close + rng.normal(0.0, 0.2, rows)
    high = np.maximum(open_, close) + np.abs(rng.normal(0.0, 0.3, rows))
    low = np.minimum(open_, close) - np.abs(rng.normal(0.0, 0.3, rows))
    volume = rng.integers(1000, 5000, rows).astype(float)
    return pd.DataFrame(
        {
            "ts": np.arange(rows) + 1_700_000_000,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _iter_output_series(group_result: dict[str, object]):
    for key, value in group_result.items():
        if isinstance(value, pd.Series):
            yield key, value
        elif isinstance(value, pd.DataFrame):
            for col in value.columns:
                yield col, value[col]


@pytest.mark.parametrize("group", CALCULATION_ORDER)
def test_group_output_schema_dtypes_float64(group: str):
    df = _make_ohlcv(500)
    calculator = GroupFeatureCalculator()
    result = calculator.calculate_group(df, group, available=GROUP_FEATURES[group])

    output_series = list(_iter_output_series(result))
    assert output_series, f"Group {group} returned no outputs"
    for name, series in output_series:
        assert series.dtype == np.float64, f"{group}:{name} dtype={series.dtype}"


def test_feature_value_ranges_top_indicators():
    df = _make_ohlcv(500)
    result = compute_features(
        df,
        specs=["rsi_14", "atr_14", "adx_14", "stoch_k", "stoch_d"],
        volatility_normalize=False,
    )

    rsi = result["rsi_14"].dropna()
    atr = result["atr_14"].dropna()
    adx = result["adx_14"].dropna()
    stoch_k = result["stoch_k"].dropna()
    stoch_d = result["stoch_d"].dropna()

    assert not rsi.empty
    assert not atr.empty

    assert ((rsi >= 0.0) & (rsi <= 100.0)).all()
    assert (atr >= 0.0).all()
    if not adx.empty:
        assert ((adx >= 0.0) & (adx <= 100.0)).all()
    if not stoch_k.empty:
        assert ((stoch_k >= 0.0) & (stoch_k <= 100.0)).all()
    if not stoch_d.empty:
        assert ((stoch_d >= 0.0) & (stoch_d <= 100.0)).all()


def test_no_lookahead_rsi_with_warmup_250():
    df = _make_ohlcv(500)
    result_full = compute_features(df, specs=["rsi_14"], volatility_normalize=False)
    result_trunc = compute_features(
        df.iloc[:300].copy(),
        specs=["rsi_14"],
        volatility_normalize=False,
    )
    pd.testing.assert_series_equal(
        result_full["rsi_14"].iloc[WARMUP:300].reset_index(drop=True),
        result_trunc["rsi_14"].iloc[WARMUP:].reset_index(drop=True),
        check_exact=False,
        atol=1e-4,
        check_names=False,
    )
