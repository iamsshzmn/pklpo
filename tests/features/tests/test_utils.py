"""
Unit tests for utils module.
"""

import numpy as np
import pandas as pd
import pytest

from src.features.utils import (
    _normalize_series_by_volatility,
    assert_frames_close,
    minmax_normalize_features,
    volatility_normalize_features,
    zscore_normalize_features,
)


class TestVolatilityNormalization:
    """Test volatility normalization functionality."""

    def test_volatility_normalize_basic(self):
        """Test basic volatility normalization."""
        df = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                "feature2": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            }
        )

        result = volatility_normalize_features(df, window=5)

        assert "feature1" in result.columns
        assert "feature2" in result.columns
        assert "close" in result.columns  # Should be excluded from normalization

        # Check that normalized features have different scales
        assert not np.array_equal(result["feature1"], df["feature1"])
        assert not np.array_equal(result["feature2"], df["feature2"])
        assert np.array_equal(result["close"], df["close"])  # Should be unchanged

    def test_volatility_normalize_empty_dataframe(self):
        """Test normalization with empty DataFrame."""
        df = pd.DataFrame()
        result = volatility_normalize_features(df)
        assert result.empty

    def test_volatility_normalize_none_dataframe(self):
        """Test normalization with None DataFrame."""
        result = volatility_normalize_features(None)
        assert result is None

    def test_volatility_normalize_constant_series(self):
        """Test normalization with constant series."""
        df = pd.DataFrame(
            {"constant_feature": [5, 5, 5, 5, 5], "varying_feature": [1, 2, 3, 4, 5]}
        )

        result = volatility_normalize_features(df, window=3)

        # Constant series should be unchanged
        assert np.array_equal(result["constant_feature"], df["constant_feature"])
        # Varying series should be normalized
        assert not np.array_equal(result["varying_feature"], df["varying_feature"])

    def test_volatility_normalize_all_nan_series(self):
        """Test normalization with all-NaN series."""
        df = pd.DataFrame(
            {
                "nan_feature": [np.nan, np.nan, np.nan, np.nan, np.nan],
                "normal_feature": [1, 2, 3, 4, 5],
            }
        )

        result = volatility_normalize_features(df, window=3)

        # NaN series should be preserved as-is
        assert result["nan_feature"].isna().all()
        # Normal series should be normalized
        assert not np.array_equal(result["normal_feature"], df["normal_feature"])

    def test_volatility_normalize_custom_columns(self):
        """Test normalization with custom column selection."""
        df = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [10, 20, 30, 40, 50],
                "exclude_me": [100, 200, 300, 400, 500],
            }
        )

        result = volatility_normalize_features(
            df, feature_columns=["feature1", "feature2"], window=3
        )

        # Only specified columns should be normalized
        assert not np.array_equal(result["feature1"], df["feature1"])
        assert not np.array_equal(result["feature2"], df["feature2"])
        assert np.array_equal(result["exclude_me"], df["exclude_me"])

    def test_volatility_normalize_exclude_columns(self):
        """Test normalization with excluded columns."""
        df = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [10, 20, 30, 40, 50],
                "exclude_me": [100, 200, 300, 400, 500],
            }
        )

        result = volatility_normalize_features(
            df, exclude_columns=["exclude_me"], window=3
        )

        # Excluded column should be unchanged
        assert np.array_equal(result["exclude_me"], df["exclude_me"])
        # Other columns should be normalized
        assert not np.array_equal(result["feature1"], df["feature1"])
        assert not np.array_equal(result["feature2"], df["feature2"])

    def test_volatility_normalize_ewm_method(self):
        """Test EWM volatility normalization method."""
        df = pd.DataFrame({"feature1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})

        result_rolling = volatility_normalize_features(
            df, window=5, method="rolling_std"
        )
        result_ewm = volatility_normalize_features(df, window=5, method="ewm_std")

        # Results should be different for different methods
        assert not np.array_equal(result_rolling["feature1"], result_ewm["feature1"])

    def test_volatility_normalize_invalid_method(self):
        """Test invalid normalization method returns original data."""
        df = pd.DataFrame({"feature1": [1, 2, 3, 4, 5]})

        # Should not raise exception, but return original data
        result = volatility_normalize_features(df, method="invalid_method")
        pd.testing.assert_series_equal(result["feature1"], df["feature1"])


class TestNormalizeSeriesByVolatility:
    """Test individual series volatility normalization."""

    def test_normalize_series_rolling_std(self):
        """Test rolling standard deviation normalization."""
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = _normalize_series_by_volatility(series, window=5, method="rolling_std")

        assert len(result) == len(series)
        assert not np.array_equal(result, series)

    def test_normalize_series_ewm_std(self):
        """Test EWM standard deviation normalization."""
        series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = _normalize_series_by_volatility(series, window=5, method="ewm_std")

        assert len(result) == len(series)
        assert not np.array_equal(result, series)

    def test_normalize_series_zero_volatility(self):
        """Test series with zero volatility."""
        series = pd.Series([5, 5, 5, 5, 5])
        result = _normalize_series_by_volatility(series, window=3, method="rolling_std")

        # Should return original series when volatility is zero
        assert np.array_equal(result, series)

    def test_normalize_series_invalid_method(self):
        """Test invalid method raises error."""
        series = pd.Series([1, 2, 3, 4, 5])

        with pytest.raises(ValueError, match="Unknown normalization method"):
            _normalize_series_by_volatility(series, method="invalid")


class TestZScoreNormalization:
    """Test Z-score normalization."""

    def test_zscore_normalize_basic(self):
        """Test basic Z-score normalization."""
        df = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [10, 20, 30, 40, 50],
                "close": [100, 101, 102, 103, 104],
            }
        )

        result = zscore_normalize_features(df)

        # Check that features are normalized (mean ≈ 0, std ≈ 1)
        assert abs(result["feature1"].mean()) < 0.1
        assert abs(result["feature2"].mean()) < 0.1
        assert abs(result["feature1"].std() - 1.0) < 0.1
        assert abs(result["feature2"].std() - 1.0) < 0.1

        # Close should be excluded
        assert np.array_equal(result["close"], df["close"])

    def test_zscore_normalize_constant_series(self):
        """Test Z-score normalization with constant series."""
        df = pd.DataFrame(
            {"constant_feature": [5, 5, 5, 5, 5], "varying_feature": [1, 2, 3, 4, 5]}
        )

        result = zscore_normalize_features(df)

        # Constant series should be unchanged (std = 0)
        assert np.array_equal(result["constant_feature"], df["constant_feature"])
        # Varying series should be normalized
        assert abs(result["varying_feature"].mean()) < 0.1


class TestMinMaxNormalization:
    """Test min-max normalization."""

    def test_minmax_normalize_basic(self):
        """Test basic min-max normalization."""
        df = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [10, 20, 30, 40, 50],
                "close": [100, 101, 102, 103, 104],
            }
        )

        result = minmax_normalize_features(df)

        # Check that features are normalized to [0, 1] range
        assert result["feature1"].min() == 0.0
        assert result["feature1"].max() == 1.0
        assert result["feature2"].min() == 0.0
        assert result["feature2"].max() == 1.0

        # Close should be excluded
        assert np.array_equal(result["close"], df["close"])

    def test_minmax_normalize_custom_range(self):
        """Test min-max normalization with custom range."""
        df = pd.DataFrame({"feature1": [1, 2, 3, 4, 5]})

        result = minmax_normalize_features(df, feature_range=(-1, 1))

        # Check that features are normalized to [-1, 1] range
        assert result["feature1"].min() == -1.0
        assert result["feature1"].max() == 1.0


class TestAssertFramesClose:
    """Test DataFrame comparison utility."""

    def test_assert_frames_close_identical(self):
        """Test identical DataFrames pass assertion."""
        df1 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        df2 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

        # Should not raise any exception
        assert_frames_close(df1, df2)

    def test_assert_frames_close_close_values(self):
        """Test close values pass assertion."""
        df1 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        df2 = pd.DataFrame({"a": [1.0001, 2.0001, 3.0001], "b": [4, 5, 6]})

        # Should not raise any exception with relaxed tolerances
        assert_frames_close(df1, df2, rtol=1e-3, atol=1e-3)

    def test_assert_frames_close_different_values(self):
        """Test different values raise assertion error."""
        df1 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        df2 = pd.DataFrame({"a": [10, 20, 30], "b": [4, 5, 6]})

        with pytest.raises(AssertionError):
            assert_frames_close(df1, df2)

    def test_assert_frames_close_with_nan(self):
        """Test DataFrames with NaN values."""
        df1 = pd.DataFrame({"a": [1, np.nan, 3], "b": [4, 5, 6]})
        df2 = pd.DataFrame({"a": [1, np.nan, 3], "b": [4, 5, 6]})

        # Should not raise any exception (NaN values are considered equal)
        assert_frames_close(df1, df2)

    def test_assert_frames_close_specific_columns(self):
        """Test comparison with specific columns."""
        df1 = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]})
        df2 = pd.DataFrame({"a": [1, 2, 3], "b": [40, 50, 60], "c": [7, 8, 9]})

        # Should not raise any exception when comparing only columns 'a' and 'c'
        assert_frames_close(df1, df2, columns=["a", "c"])

        # Should raise exception when comparing all columns
        with pytest.raises(AssertionError):
            assert_frames_close(df1, df2)

    def test_assert_frames_close_different_indexes(self):
        """Test DataFrames with different indexes."""
        df1 = pd.DataFrame({"a": [1, 2, 3]}, index=[0, 1, 2])
        df2 = pd.DataFrame({"a": [2, 3, 4]}, index=[1, 2, 3])

        # Should only compare common index values (indices 1, 2)
        # df1[1,2] = [2, 3], df2[1,2] = [2, 3] - should match
        assert_frames_close(df1, df2)
