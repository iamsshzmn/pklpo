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
from src.features.ports import (
    FeatureCalculatorBackend,
    FeatureSaveObservation,
    FeatureSaveObserver,
    FeatureSaveValidator,
    IndicatorRepository,
    RepositoryStorageProfile,
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


class TestFeatureCalculatorBackendProtocol:
    """Tests for FeatureCalculatorBackend protocol."""

    def test_valid_implementation(self):
        """Class with backend wrapper contract is instance of protocol."""
        class Backend:
            backend_id = "talib"

            def __call__(self, compute_fn, df_ohlcv, specs=None, **kwargs):
                return compute_fn(df_ohlcv, specs=specs, **kwargs)

        assert isinstance(Backend(), FeatureCalculatorBackend)

    def test_invalid_implementation(self):
        """Class without callable wrapper is not instance."""
        class NotBackend:
            backend_id = "talib"

        assert not isinstance(NotBackend(), FeatureCalculatorBackend)

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


class TestFeatureSaveValidatorProtocol:
    """Tests for FeatureSaveValidator protocol."""

    def test_valid_implementation(self):
        class SaveValidator:
            def validate_save_dataframe(self, df, symbol, timeframe):
                return {"valid": True}

        assert isinstance(SaveValidator(), FeatureSaveValidator)

    def test_invalid_implementation(self):
        class InvalidSaveValidator:
            def validate(self, df):
                return {"valid": True}

        assert not isinstance(InvalidSaveValidator(), FeatureSaveValidator)


class TestFeatureSaveObservationProtocol:
    """Tests for FeatureSaveObservation protocol."""

    def test_valid_implementation(self):
        class Observation:
            def record_success(self, *, rows_processed, rows_saved):
                return None

            def record_error(self, error):
                return None

        assert isinstance(Observation(), FeatureSaveObservation)

    def test_invalid_implementation(self):
        class InvalidObservation:
            def record_success(self, *, rows_processed, rows_saved):
                return None

        assert not isinstance(InvalidObservation(), FeatureSaveObservation)


class TestFeatureSaveObserverProtocol:
    """Tests for FeatureSaveObserver protocol."""

    def test_valid_implementation(self):
        class Observer:
            def observe(self, *, operation, symbol, timeframe, df, log_memory=False):
                class _Ctx:
                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, exc_tb):
                        return None

                    def record_success(self, *, rows_processed, rows_saved):
                        return None

                    def record_error(self, error):
                        return None

                return _Ctx()

        assert isinstance(Observer(), FeatureSaveObserver)

    def test_invalid_implementation(self):
        class InvalidObserver:
            def create(self, df):
                return None

        assert not isinstance(InvalidObserver(), FeatureSaveObserver)


class TestIndicatorRepositoryProtocol:
    """Tests for IndicatorRepository protocol."""

    @pytest.mark.asyncio
    async def test_valid_implementation(self):
        class Repo:
            def describe_storage(self):
                return RepositoryStorageProfile(
                    backend="sqlalchemy",
                    targets=("indicators",),
                )

            async def save_batch(self, records, symbol, timeframe):
                return len(records)

            async def save_batch_from_df(self, df, symbol, timeframe):
                return len(df)

            async def validate_connection(self):
                return {"valid": True}

            async def verify_integrity(self, symbol, timeframe):
                return {"integrity_ok": True}

        assert isinstance(Repo(), IndicatorRepository)

    def test_invalid_implementation(self):
        class IncompleteRepo:
            async def save_batch(self, records, symbol, timeframe):
                return len(records)

        assert not isinstance(IncompleteRepo(), IndicatorRepository)


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
