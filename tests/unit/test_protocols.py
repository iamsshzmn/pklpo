"""
Unit tests for Protocols (Task 7).

Tests the runtime_checkable Protocol interfaces.
"""

import pandas as pd
import pytest

from src.features.domain.protocols import (
    BatchIndicatorCalculator,
    FeatureCalculator,
    FeatureNormalizer,
    IndicatorCalculator,
    OHLCVValidator,
)


class TestIndicatorCalculatorProtocol:
    """Tests for IndicatorCalculator protocol."""

    def test_valid_implementation(self):
        """Class with correct signature is instance of protocol."""
        class MyCalculator:
            def calculate(self, df_ohlcv, **params):
                return df_ohlcv["close"]

        calc = MyCalculator()
        assert isinstance(calc, IndicatorCalculator)

    def test_invalid_implementation(self):
        """Class without method is not instance."""
        class NotCalculator:
            pass

        assert not isinstance(NotCalculator(), IndicatorCalculator)


class TestBatchIndicatorCalculatorProtocol:
    """Tests for BatchIndicatorCalculator protocol."""

    def test_valid_implementation(self):
        """Class with correct signature is instance of protocol."""
        class MyBatch:
            def calculate_many(self, df_ohlcv, names, **params):
                return {}

        batch = MyBatch()
        assert isinstance(batch, BatchIndicatorCalculator)

    def test_invalid_implementation(self):
        """Class without method is not instance."""
        class NotBatch:
            def calculate(self, df):  # Wrong method name
                return {}

        assert not isinstance(NotBatch(), BatchIndicatorCalculator)


class TestFeatureCalculatorProtocol:
    """Tests for FeatureCalculator protocol (Task 7)."""

    def test_valid_implementation(self):
        """Class with correct signature is instance of protocol."""
        class MyFeatureCalc:
            def calculate(self, df_ohlcv, specs=None, *,
                         volatility_normalize=False, normalize_window=20, **kwargs):
                return df_ohlcv

        fc = MyFeatureCalc()
        assert isinstance(fc, FeatureCalculator)

    def test_minimal_implementation(self):
        """Minimal implementation with just required signature."""
        class MinimalCalc:
            def calculate(self, df_ohlcv, specs=None, **kwargs):
                return df_ohlcv

        # Note: Python's Protocol doesn't strictly check keyword-only args
        calc = MinimalCalc()
        assert isinstance(calc, FeatureCalculator)

    def test_invalid_implementation(self):
        """Class without calculate method is not instance."""
        class NotFeatureCalc:
            def compute(self, df):  # Wrong method name
                return df

        assert not isinstance(NotFeatureCalc(), FeatureCalculator)

    def test_can_call_method(self):
        """Protocol implementation can be called."""
        class WorkingCalc:
            def calculate(self, df_ohlcv, specs=None, **kwargs):
                return df_ohlcv.copy()

        calc = WorkingCalc()
        df = pd.DataFrame({"close": [1, 2, 3]})

        result = calc.calculate(df)
        assert result.equals(df)


class TestOHLCVValidatorProtocol:
    """Tests for OHLCVValidator protocol."""

    def test_valid_implementation(self):
        """Class with correct signature is instance of protocol."""
        class MyValidator:
            def validate(self, df):
                return True

        v = MyValidator()
        assert isinstance(v, OHLCVValidator)

    def test_invalid_implementation(self):
        """Class without validate method is not instance."""
        class NotValidator:
            def check(self, df):
                return True

        assert not isinstance(NotValidator(), OHLCVValidator)

    def test_validate_returns_bool(self):
        """Validate method returns boolean."""
        class BoolValidator:
            def validate(self, df):
                return df is not None and not df.empty

        v = BoolValidator()
        df = pd.DataFrame({"a": [1, 2, 3]})

        assert v.validate(df) is True
        assert v.validate(pd.DataFrame()) is False


class TestFeatureNormalizerProtocol:
    """Tests for FeatureNormalizer protocol."""

    def test_valid_implementation(self):
        """Class with correct signature is instance of protocol."""
        class MyNorm:
            def normalize(self, df, window=20):
                return df

        n = MyNorm()
        assert isinstance(n, FeatureNormalizer)

    def test_invalid_implementation(self):
        """Class without normalize method is not instance."""
        class NotNormalizer:
            def standardize(self, df):
                return df

        assert not isinstance(NotNormalizer(), FeatureNormalizer)

    def test_normalize_with_default_window(self):
        """Normalize can be called with default window."""
        class SimpleNorm:
            def normalize(self, df, window=20):
                # Simple normalization: subtract mean
                return df - df.mean()

        n = SimpleNorm()
        df = pd.DataFrame({"a": [10, 20, 30]})

        result = n.normalize(df)
        assert result["a"].mean() == pytest.approx(0, abs=1e-10)

    def test_normalize_with_custom_window(self):
        """Normalize accepts custom window parameter."""
        window_used = None

        class TrackingNorm:
            def normalize(self, df, window=20):
                nonlocal window_used
                window_used = window
                return df

        n = TrackingNorm()
        df = pd.DataFrame({"a": [1, 2, 3]})

        n.normalize(df, window=50)
        assert window_used == 50


class TestProtocolCombinations:
    """Tests for classes implementing multiple protocols."""

    def test_class_implements_multiple_protocols(self):
        """Class can implement multiple protocols."""
        class MultiProtocol:
            def validate(self, df):
                return True

            def normalize(self, df, window=20):
                return df

        obj = MultiProtocol()

        assert isinstance(obj, OHLCVValidator)
        assert isinstance(obj, FeatureNormalizer)

    def test_all_protocols_independent(self):
        """Each protocol check is independent."""
        class OnlyValidator:
            def validate(self, df):
                return True

        obj = OnlyValidator()

        assert isinstance(obj, OHLCVValidator)
        assert not isinstance(obj, FeatureNormalizer)
        assert not isinstance(obj, FeatureCalculator)
