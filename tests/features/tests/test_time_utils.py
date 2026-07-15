"""
Unit tests for time utilities.
"""

import numpy as np
import pandas as pd

from src.features.utils.time_utils import (
    ensure_ts_column,
    get_timestamp_info,
    normalize_timestamp_to_seconds,
    validate_timestamp_consistency,
)


class TestNormalizeTimestampToSeconds:
    """Test timestamp normalization to seconds."""

    def test_none_input(self):
        """Test None input returns None."""
        assert normalize_timestamp_to_seconds(None) is None

    def test_pandas_timestamp(self):
        """Test pandas Timestamp conversion."""
        ts = pd.Timestamp("2023-01-01 12:00:00", tz="UTC")
        expected = int(ts.timestamp())
        assert normalize_timestamp_to_seconds(ts) == expected

    def test_milliseconds_input(self):
        """Test milliseconds input (large number)."""
        ms_timestamp = 1672574400000  # 2023-01-01 12:00:00 in ms
        expected_seconds = 1672574400
        assert normalize_timestamp_to_seconds(ms_timestamp) == expected_seconds

    def test_seconds_input(self):
        """Test seconds input (small number)."""
        seconds_timestamp = 1672574400  # 2023-01-01 12:00:00 in s
        assert normalize_timestamp_to_seconds(seconds_timestamp) == seconds_timestamp

    def test_string_input(self):
        """Test string timestamp parsing."""
        ts_str = "2023-01-01 12:00:00"
        result = normalize_timestamp_to_seconds(ts_str)
        assert isinstance(result, int)
        assert result > 0

    def test_series_input(self):
        """Test pandas Series input."""
        timestamps = [1672574400000, 1672574460000, 1672574520000]  # ms
        series = pd.Series(timestamps)
        result = normalize_timestamp_to_seconds(series)

        assert isinstance(result, pd.Series)
        assert len(result) == 3
        assert all(isinstance(x, int) for x in result)
        assert result.iloc[0] == 1672574400  # converted to seconds

    def test_nan_input(self):
        """Test NaN input handling."""
        result = normalize_timestamp_to_seconds(np.nan)
        assert result is None

        # Test Series with NaN
        series = pd.Series([1672574400000, np.nan, 1672574520000])
        result = normalize_timestamp_to_seconds(series)
        assert pd.isna(result.iloc[1])


class TestEnsureTsColumn:
    """Test ensuring ts column in DataFrame."""

    def test_existing_ts_column(self):
        """Test when ts column already exists."""
        df = pd.DataFrame(
            {"ts": [1672574400000, 1672574460000, 1672574520000], "value": [1, 2, 3]}
        )
        result = ensure_ts_column(df)

        assert "ts" in result.columns
        assert result["ts"].dtype == "int64"

    def test_timestamp_column_conversion(self):
        """Test converting timestamp column to ts."""
        df = pd.DataFrame(
            {
                "timestamp": [1672574400000, 1672574460000, 1672574520000],  # ms
                "value": [1, 2, 3],
            }
        )
        result = ensure_ts_column(df, timestamp_col="timestamp")

        assert "ts" in result.columns
        assert result["ts"].iloc[0] == 1672574400000  # normalized to milliseconds

    def test_datetime_index_conversion(self):
        """Test using datetime index as timestamp source."""
        dates = pd.date_range("2023-01-01", periods=3, freq="1min")
        df = pd.DataFrame({"value": [1, 2, 3]}, index=dates)
        result = ensure_ts_column(df)

        assert "ts" in result.columns
        assert len(result["ts"]) == 3
        # Check that all values are integers (including nullable integers)
        assert all(isinstance(x, int | np.integer) or pd.isna(x) for x in result["ts"])

    def test_fallback_sequential_ts(self):
        """Test fallback to sequential ts from index."""
        df = pd.DataFrame({"value": [1, 2, 3]})
        result = ensure_ts_column(df)

        assert "ts" in result.columns
        assert result["ts"].iloc[0] == 0
        assert result["ts"].iloc[1] == 1000
        assert result["ts"].iloc[2] == 2000


class TestValidateTimestampConsistency:
    """Test timestamp consistency validation."""

    def test_valid_monotonic_timestamps(self):
        """Test valid monotonic timestamps."""
        df = pd.DataFrame(
            {"ts": [1672574400000, 1672574460000, 1672574520000], "value": [1, 2, 3]}
        )
        assert validate_timestamp_consistency(df) is True

    def test_non_monotonic_timestamps(self):
        """Test non-monotonic timestamps."""
        df = pd.DataFrame(
            {
                "ts": [1672574400000, 1672574520000, 1672574460000],  # not monotonic
                "value": [1, 2, 3],
            }
        )
        assert validate_timestamp_consistency(df) is False

    def test_nan_timestamps(self):
        """Test NaN timestamps."""
        df = pd.DataFrame(
            {"ts": [1672574400000, np.nan, 1672574520000], "value": [1, 2, 3]}
        )
        assert validate_timestamp_consistency(df) is False

    def test_negative_timestamps(self):
        """Test negative timestamps."""
        df = pd.DataFrame(
            {"ts": [-1000, 1672574400000, 1672574520000], "value": [1, 2, 3]}
        )
        assert validate_timestamp_consistency(df) is False

    def test_future_timestamps(self):
        """Test timestamps beyond year 2100."""
        df = pd.DataFrame(
            {
                "ts": [1672574400000, 1672574520000, 5000000000000],  # year 2128
                "value": [1, 2, 3],
            }
        )
        assert validate_timestamp_consistency(df) is False

    def test_missing_ts_column(self):
        """Test missing ts column."""
        df = pd.DataFrame({"value": [1, 2, 3]})
        assert validate_timestamp_consistency(df) is False


class TestGetTimestampInfo:
    """Test timestamp information extraction."""

    def test_valid_timestamps_info(self):
        """Test getting info for valid timestamps."""
        df = pd.DataFrame(
            {"ts": [1672574400000, 1672574460000, 1672574520000], "value": [1, 2, 3]}
        )
        info = get_timestamp_info(df)

        assert info["count"] == 3
        assert info["non_null_count"] == 3
        assert info["null_count"] == 0
        assert info["min"] == 1672574400000
        assert info["max"] == 1672574520000
        assert info["is_monotonic"] is True
        assert "min_date" in info
        assert "max_date" in info

    def test_mixed_timestamps_info(self):
        """Test getting info for timestamps with NaN."""
        df = pd.DataFrame(
            {"ts": [1672574400000, np.nan, 1672574520000], "value": [1, 2, 3]}
        )
        info = get_timestamp_info(df)

        assert info["count"] == 3
        assert info["non_null_count"] == 2
        assert info["null_count"] == 1
        assert info["is_monotonic"] is False

    def test_missing_column(self):
        """Test getting info for missing column."""
        df = pd.DataFrame({"value": [1, 2, 3]})
        info = get_timestamp_info(df)

        assert "error" in info
        assert "Column 'ts' not found" in info["error"]
