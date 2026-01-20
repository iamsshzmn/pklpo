"""
Tests for name mapping utilities.
"""

import pandas as pd

from src.features.name_mapping import (
    INDICATOR_NAME_MAPPING,
    MULTI_OUTPUT_INDICATORS,
    check_indicator_capability,
    get_available_indicators,
    get_version_info,
    normalize_indicator_name,
    safe_indicator_call,
    validate_versions,
)


class TestNormalizeIndicatorName:
    """Test indicator name normalization."""

    def test_ema_normalization(self):
        """Test EMA indicator name normalization."""
        assert normalize_indicator_name("EMA_14") == "ema_14"
        assert normalize_indicator_name("EMA_21") == "ema_21"
        assert normalize_indicator_name("EMA") == "ema"

    def test_sma_normalization(self):
        """Test SMA indicator name normalization."""
        assert normalize_indicator_name("SMA_20") == "sma_20"
        assert normalize_indicator_name("SMA_50") == "sma_50"
        assert normalize_indicator_name("SMA") == "sma"

    def test_rsi_normalization(self):
        """Test RSI indicator name normalization."""
        assert normalize_indicator_name("RSI_14") == "rsi_14"
        assert normalize_indicator_name("RSI_21") == "rsi_21"
        assert normalize_indicator_name("RSI") == "rsi"

    def test_macd_normalization(self):
        """Test MACD indicator name normalization."""
        assert normalize_indicator_name("MACD_12_26_9") == "macd"
        assert normalize_indicator_name("MACDS_12_26_9") == "macd_signal"
        assert normalize_indicator_name("MACDH_12_26_9") == "macd_histogram"

    def test_stochastic_normalization(self):
        """Test Stochastic indicator name normalization."""
        assert normalize_indicator_name("STOCHK_14_3_3") == "stoch_k"
        assert normalize_indicator_name("STOCHD_14_3_3") == "stoch_d"
        assert normalize_indicator_name("STOCHRSIK_14_14_3_3") == "stochrsi_k"
        assert normalize_indicator_name("STOCHRSID_14_14_3_3") == "stochrsi_d"

    def test_bollinger_bands_normalization(self):
        """Test Bollinger Bands indicator name normalization."""
        assert normalize_indicator_name("BBANDS_20_2.0_U") == "bb_upper"
        assert normalize_indicator_name("BBANDS_20_2.0_M") == "bb_middle"
        assert normalize_indicator_name("BBANDS_20_2.0_L") == "bb_lower"
        assert normalize_indicator_name("BBANDS_20_2.0_W") == "bb_width"
        assert normalize_indicator_name("BBANDS_20_2.0_P") == "bb_percent"

    def test_adx_normalization(self):
        """Test ADX indicator name normalization."""
        assert normalize_indicator_name("ADX_14") == "adx_14"
        assert normalize_indicator_name("ADX_21") == "adx_21"
        assert normalize_indicator_name("DMP_14") == "adx_pos_di"
        assert normalize_indicator_name("DMN_14") == "adx_neg_di"

    def test_volume_indicators_normalization(self):
        """Test volume indicator name normalization."""
        assert normalize_indicator_name("OBV") == "obv"
        assert normalize_indicator_name("VWAP") == "vwap"
        assert normalize_indicator_name("MFI_14") == "mfi_14"
        assert normalize_indicator_name("CMF_20") == "cmf_20"

    def test_volatility_indicators_normalization(self):
        """Test volatility indicator name normalization."""
        assert normalize_indicator_name("ATR_14") == "atr_14"
        assert normalize_indicator_name("NATR_14") == "natr_14"
        assert normalize_indicator_name("TRANGE") == "trange"

    def test_candle_patterns_normalization(self):
        """Test candlestick pattern name normalization."""
        assert normalize_indicator_name("CDLDOJI") == "cdl_doji"
        assert normalize_indicator_name("CDLHAMMER") == "cdl_hammer"
        assert normalize_indicator_name("CDLENGULFING") == "cdl_engulfing"
        assert normalize_indicator_name("CDLMORNINGSTAR") == "cdl_morningstar"

    def test_fallback_normalization(self):
        """Test fallback to snake_case for unknown indicators."""
        assert normalize_indicator_name("UNKNOWN_INDICATOR") == "unknown_indicator"
        assert normalize_indicator_name("Custom Indicator") == "custom_indicator"
        assert normalize_indicator_name("test-indicator") == "test_indicator"

    def test_edge_cases(self):
        """Test edge cases in name normalization."""
        assert normalize_indicator_name("") == ""
        assert normalize_indicator_name("   ") == ""  # strip() removes whitespace
        assert normalize_indicator_name("123") == "123"
        assert normalize_indicator_name("EMA_") == "ema_"


class TestCheckIndicatorCapability:
    """Test indicator capability checking."""

    def test_known_indicators(self):
        """Test capability check for known indicators."""
        # These should be available in pandas_ta
        assert check_indicator_capability("ema") is True
        assert check_indicator_capability("sma") is True
        assert check_indicator_capability("rsi") is True
        assert check_indicator_capability("macd") is True

    def test_unknown_indicators(self):
        """Test capability check for unknown indicators."""
        assert check_indicator_capability("nonexistent_indicator") is False
        assert check_indicator_capability("fake_ta_function") is False

    def test_capability_caching(self):
        """Test that capability results are cached."""
        # First call should cache the result
        result1 = check_indicator_capability("ema")
        result2 = check_indicator_capability("ema")
        assert result1 == result2

        # Unknown indicator should also be cached
        result3 = check_indicator_capability("fake_indicator")
        result4 = check_indicator_capability("fake_indicator")
        assert result3 == result4


class TestGetAvailableIndicators:
    """Test getting available indicators."""

    def test_available_indicators_not_empty(self):
        """Test that we get some available indicators."""
        indicators = get_available_indicators()
        assert len(indicators) > 0
        assert isinstance(indicators, set)

    def test_known_indicators_in_available(self):
        """Test that known indicators are in available list."""
        indicators = get_available_indicators()
        # These should definitely be available
        expected = {"ema", "sma", "rsi", "macd", "atr", "obv"}
        assert expected.issubset(indicators)


class TestSafeIndicatorCall:
    """Test safe indicator calling."""

    def test_safe_call_known_indicator(self):
        """Test safe call with known indicator."""
        # Create test data
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

        # Call EMA (should work)
        result = safe_indicator_call("ema", data, length=5)
        assert result is not None
        assert isinstance(result, pd.Series)
        assert len(result) == len(data)

    def test_safe_call_unknown_indicator(self):
        """Test safe call with unknown indicator."""
        data = pd.Series([1, 2, 3, 4, 5])

        # Call unknown indicator (should return None or NaN series)
        result = safe_indicator_call("nonexistent_indicator", data)
        # Should either return None or NaN series
        if result is not None:
            assert isinstance(result, pd.Series)
            assert result.isna().all()

    def test_safe_call_with_error(self):
        """Test safe call that causes an error."""
        # Call with invalid parameters
        result = safe_indicator_call("ema", None)
        assert result is None or (isinstance(result, pd.Series) and result.isna().all())


class TestVersionInfo:
    """Test version information functions."""

    def test_get_version_info(self):
        """Test getting version information."""
        version_info = get_version_info()

        assert "pandas_ta" in version_info
        assert "pandas" in version_info
        assert "expected_pandas_ta" in version_info
        assert "expected_pandas" in version_info

        # Check that versions are strings
        for _key, value in version_info.items():
            assert isinstance(value, str)

    def test_validate_versions(self):
        """Test version validation."""
        # This test might pass or fail depending on actual versions
        # We just check that it returns a boolean
        result = validate_versions()
        assert isinstance(result, bool)


class TestIndicatorMappings:
    """Test indicator mapping constants."""

    def test_indicator_name_mapping_not_empty(self):
        """Test that indicator name mapping is not empty."""
        assert len(INDICATOR_NAME_MAPPING) > 0
        assert isinstance(INDICATOR_NAME_MAPPING, dict)

    def test_multi_output_indicators_not_empty(self):
        """Test that multi-output indicators mapping is not empty."""
        assert len(MULTI_OUTPUT_INDICATORS) > 0
        assert isinstance(MULTI_OUTPUT_INDICATORS, dict)

    def test_multi_output_indicators_structure(self):
        """Test structure of multi-output indicators."""
        for _indicator, outputs in MULTI_OUTPUT_INDICATORS.items():
            assert isinstance(outputs, list)
            assert len(outputs) > 0
            for output in outputs:
                assert isinstance(output, str)

    def test_common_indicators_in_mapping(self):
        """Test that common indicators are in the mapping."""
        common_indicators = ["EMA", "SMA", "RSI", "MACD", "ATR", "OBV", "VWAP"]
        for indicator in common_indicators:
            assert indicator in INDICATOR_NAME_MAPPING


class TestIntegration:
    """Integration tests for name mapping."""

    def test_full_normalization_workflow(self):
        """Test complete workflow from raw name to normalized name."""
        raw_names = [
            "EMA_14",
            "RSI_21",
            "MACD_12_26_9",
            "BBANDS_20_2.0_U",
            "STOCHK_14_3_3",
            "CDLDOJI",
        ]

        expected_names = ["ema_14", "rsi_21", "macd", "bb_upper", "stoch_k", "cdl_doji"]

        for raw, expected in zip(raw_names, expected_names, strict=False):
            result = normalize_indicator_name(raw)
            assert (
                result == expected
            ), f"Failed for {raw}: expected {expected}, got {result}"

    def test_capability_and_normalization_integration(self):
        """Test integration of capability checking and normalization."""
        # Test with known available indicator
        if check_indicator_capability("ema"):
            normalized = normalize_indicator_name("EMA_14")
            assert normalized == "ema_14"

        # Test with potentially unavailable indicator
        if not check_indicator_capability("nonexistent"):
            # Should still normalize the name
            normalized = normalize_indicator_name("NONEXISTENT_14")
            assert normalized == "nonexistent_14"
