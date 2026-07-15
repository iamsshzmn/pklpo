"""Test Stage A indicators: overlap, statistics, performance, squeeze, stochrsi."""

import pandas as pd
import pytest

from src.features import compute_features


class TestStageA:
    """Test Stage A indicators with deterministic OHLCV data."""

    @pytest.fixture
    def sample_data(self):
        """Create deterministic OHLCV data for fast CI."""
        rows = 1000
        base = pd.Series(range(rows), dtype="float64")
        close = 100.0 + base * 0.1 + (base % 17) * 0.01
        open_ = close.shift(1).fillna(close.iloc[0])
        high = pd.concat([open_, close], axis=1).max(axis=1) + 0.5
        low = pd.concat([open_, close], axis=1).min(axis=1) - 0.5
        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000.0 + (base % 23) * 10.0,
                "ts": 1_700_000_000_000
                + pd.Series(range(rows), dtype="int64") * 60_000,
            }
        )

    def test_overlap_indicators(self, sample_data):
        """Test overlap indicators: hl2, hlc3, ohlc4, wcp."""
        overlap_specs = ["hl2", "hlc3", "ohlc4", "wcp"]

        result = compute_features(
            sample_data, specs=overlap_specs, volatility_normalize=False
        )

        for spec in overlap_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        assert (
            abs(
                result["hl2"].iloc[-1]
                - (result["high"].iloc[-1] + result["low"].iloc[-1]) / 2
            )
            < 1e-10
        )
        assert (
            abs(
                result["hlc3"].iloc[-1]
                - (
                    result["high"].iloc[-1]
                    + result["low"].iloc[-1]
                    + result["close"].iloc[-1]
                )
                / 3
            )
            < 1e-10
        )
        assert (
            abs(
                result["ohlc4"].iloc[-1]
                - (
                    result["open"].iloc[-1]
                    + result["high"].iloc[-1]
                    + result["low"].iloc[-1]
                    + result["close"].iloc[-1]
                )
                / 4
            )
            < 1e-10
        )

        for alias in ["midpoint", "midprice"]:
            alias_result = compute_features(
                sample_data, specs=[alias], volatility_normalize=False
            )
            assert "hl2" in alias_result.columns, f"Missing normalized alias: {alias}"
            assert abs(alias_result["hl2"].iloc[-1] - result["hl2"].iloc[-1]) < 1e-10

    def test_statistics_indicators(self, sample_data):
        """Test statistics indicators."""
        stats_specs = [
            "median_20",
            "mad_20",
            "stdev_20",
            "variance_20",
            "skew_20",
            "kurtosis_20",
            "zscore_20",
        ]

        result = compute_features(
            sample_data, specs=stats_specs, volatility_normalize=False
        )

        for spec in stats_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        variance = result["variance_20"].dropna()
        stdev = result["stdev_20"].dropna()
        if len(variance) > 0 and len(stdev) > 0:
            assert abs(variance.iloc[-1] - stdev.iloc[-1] ** 2) < 1e-6

    def test_performance_indicators(self, sample_data):
        """Test performance indicators."""
        perf_specs = ["log_return", "percent_return", "trend_return_20", "drawdown"]

        result = compute_features(
            sample_data, specs=perf_specs, volatility_normalize=False
        )

        for spec in perf_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        drawdown = result["drawdown"].dropna()
        if len(drawdown) > 0:
            assert (drawdown <= 0).all(), "Drawdown should be <= 0"

    def test_squeeze_indicators(self, sample_data):
        """Test squeeze indicators: ttm_squeeze_on, ttm_squeeze_value, ttm_squeeze_hist."""
        squeeze_specs = ["ttm_squeeze_on", "ttm_squeeze_value", "ttm_squeeze_hist"]

        result = compute_features(
            sample_data, specs=squeeze_specs, volatility_normalize=False
        )

        for spec in squeeze_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        squeeze_on = result["ttm_squeeze_on"].dropna()
        if len(squeeze_on) > 0:
            assert squeeze_on.isin([0, 1]).all(), "squeeze_on should be 0 or 1"

    def test_stochrsi_indicators(self, sample_data):
        """Test StochRSI indicators: stochrsi_k, stochrsi_d."""
        stochrsi_specs = ["stochrsi_k", "stochrsi_d"]

        result = compute_features(
            sample_data, specs=stochrsi_specs, volatility_normalize=False
        )

        for spec in stochrsi_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        for spec in stochrsi_specs:
            values = result[spec].dropna()
            if len(values) > 0:
                assert values.min() >= -1e-9 and values.max() <= 100 + 1e-9, (
                    f"{spec} should be in range [0, 100]"
                )

    def test_stage_a_all_together(self, sample_data):
        """Test all Stage A indicators together."""
        all_specs = [
            "hl2",
            "hlc3",
            "ohlc4",
            "wcp",
            "median_20",
            "mad_20",
            "stdev_20",
            "variance_20",
            "skew_20",
            "kurtosis_20",
            "zscore_20",
            "log_return",
            "percent_return",
            "trend_return_20",
            "drawdown",
            "ttm_squeeze_on",
            "ttm_squeeze_value",
            "ttm_squeeze_hist",
            "stochrsi_k",
            "stochrsi_d",
        ]

        result = compute_features(
            sample_data, specs=all_specs, volatility_normalize=False
        )

        for spec in all_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
