"""
Unit tests for ValidationChain (Task 12).

Tests the Chain of Responsibility pattern for validators.
"""

import numpy as np
import pandas as pd

from src.features.validation.chain import (
    MinRowsValidator,
    NaNRatioValidator,
    OHLCVValidator,
    TimestampValidator,
    ValidationChain,
    ValidationResult,
    Validator,
    create_default_chain,
    create_strict_chain,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_default_valid(self):
        """Default result is valid with empty lists."""
        result = ValidationResult()

        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.validator_name == ""
        assert result.details == {}

    def test_add_error_marks_invalid(self):
        """add_error marks result as invalid."""
        result = ValidationResult()
        result.add_error("Test error")

        assert result.is_valid is False
        assert "Test error" in result.errors

    def test_add_warning_stays_valid(self):
        """add_warning doesn't affect validity."""
        result = ValidationResult()
        result.add_warning("Test warning")

        assert result.is_valid is True
        assert "Test warning" in result.warnings

    def test_merge_combines_errors(self):
        """merge combines errors from both results."""
        r1 = ValidationResult()
        r1.add_error("E1")

        r2 = ValidationResult()
        r2.add_error("E2")

        r1.merge(r2)

        assert "E1" in r1.errors
        assert "E2" in r1.errors

    def test_merge_combines_warnings(self):
        """merge combines warnings from both results."""
        r1 = ValidationResult()
        r1.add_warning("W1")

        r2 = ValidationResult()
        r2.add_warning("W2")

        r1.merge(r2)

        assert "W1" in r1.warnings
        assert "W2" in r1.warnings

    def test_merge_inherits_invalid_state(self):
        """merge inherits invalid state from other."""
        r1 = ValidationResult(is_valid=True)

        r2 = ValidationResult(is_valid=False)
        r2.add_error("Error")

        r1.merge(r2)

        assert r1.is_valid is False

    def test_merge_updates_details(self):
        """merge combines details dictionaries."""
        r1 = ValidationResult()
        r1.details["key1"] = "value1"

        r2 = ValidationResult()
        r2.details["key2"] = "value2"

        r1.merge(r2)

        assert r1.details["key1"] == "value1"
        assert r1.details["key2"] == "value2"


class TestOHLCVValidator:
    """Tests for OHLCVValidator."""

    def test_valid_dataframe(self, ohlcv_basic):
        """Valid OHLCV passes validation."""
        validator = OHLCVValidator()
        result = validator.validate(ohlcv_basic)

        assert result.is_valid is True
        assert result.details["row_count"] == 3
        assert result.details["column_count"] == 5

    def test_none_dataframe(self):
        """None DataFrame fails validation."""
        validator = OHLCVValidator()
        result = validator.validate(None)

        assert result.is_valid is False
        assert any("None" in e for e in result.errors)

    def test_empty_dataframe(self, empty_df):
        """Empty DataFrame fails validation."""
        validator = OHLCVValidator()
        result = validator.validate(empty_df)

        assert result.is_valid is False
        assert any("empty" in e.lower() for e in result.errors)

    def test_missing_columns(self, ohlcv_missing_columns):
        """Missing required columns fails validation."""
        validator = OHLCVValidator()
        result = validator.validate(ohlcv_missing_columns)

        assert result.is_valid is False
        assert any("Missing" in e for e in result.errors)

    def test_high_null_ratio_error(self):
        """More than 50% null values causes error."""
        df = pd.DataFrame(
            {
                "open": [100.0, np.nan, np.nan, np.nan, np.nan],  # 80% null
                "high": [105.0, 106.0, 107.0, 108.0, 109.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [104.0, 105.0, 106.0, 107.0, 108.0],
                "volume": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
            }
        )

        validator = OHLCVValidator()
        result = validator.validate(df)

        assert result.is_valid is False
        assert any(">50%" in e for e in result.errors)

    def test_medium_null_ratio_warning(self):
        """Between 10% and 50% null values causes warning."""
        df = pd.DataFrame(
            {
                "open": [100.0, np.nan, 102.0, 103.0, 104.0],  # 20% null
                "high": [105.0, 106.0, 107.0, 108.0, 109.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [104.0, 105.0, 106.0, 107.0, 108.0],
                "volume": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
            }
        )

        validator = OHLCVValidator()
        result = validator.validate(df)

        assert result.is_valid is True  # Warning only
        assert any(">10%" in w for w in result.warnings)

    def test_should_stop_on_failure(self):
        """OHLCVValidator stops chain on failure."""
        validator = OHLCVValidator()
        assert validator.should_stop_on_failure() is True

    def test_name_property(self):
        """Validator has correct name."""
        validator = OHLCVValidator()
        assert validator.name == "ohlcv"


class TestMinRowsValidator:
    """Tests for MinRowsValidator."""

    def test_sufficient_rows(self):
        """Sufficient rows passes validation."""
        df = pd.DataFrame({"a": range(50)})
        validator = MinRowsValidator(min_rows=20)

        result = validator.validate(df)

        assert result.is_valid is True

    def test_exact_min_rows(self):
        """Exact minimum rows passes validation."""
        df = pd.DataFrame({"a": range(20)})
        validator = MinRowsValidator(min_rows=20)

        result = validator.validate(df)

        assert result.is_valid is True

    def test_insufficient_rows(self):
        """Insufficient rows fails validation."""
        df = pd.DataFrame({"a": range(10)})
        validator = MinRowsValidator(min_rows=20)

        result = validator.validate(df)

        assert result.is_valid is False
        assert "Insufficient rows" in result.errors[0]
        assert "10 < 20" in result.errors[0]

    def test_none_dataframe(self):
        """None DataFrame fails validation."""
        validator = MinRowsValidator(min_rows=20)
        result = validator.validate(None)

        assert result.is_valid is False

    def test_should_stop_on_failure(self):
        """MinRowsValidator stops chain on failure."""
        validator = MinRowsValidator()
        assert validator.should_stop_on_failure() is True

    def test_custom_min_rows(self):
        """Custom min_rows is respected."""
        validator = MinRowsValidator(min_rows=100)
        df = pd.DataFrame({"a": range(50)})

        result = validator.validate(df)

        assert result.is_valid is False


class TestTimestampValidator:
    """Tests for TimestampValidator."""

    def test_valid_timestamps(self, ohlcv_with_ts):
        """Valid monotonic timestamps pass validation."""
        validator = TimestampValidator()
        result = validator.validate(ohlcv_with_ts)

        assert result.is_valid is True
        assert result.details["timestamp_column"] == "ts"
        assert result.details["duplicate_count"] == 0

    def test_no_timestamp_column(self, ohlcv_basic):
        """Missing timestamp column causes warning."""
        validator = TimestampValidator()
        result = validator.validate(ohlcv_basic)

        assert result.is_valid is True  # Warning only
        assert any("No timestamp" in w for w in result.warnings)

    def test_duplicate_timestamps(self):
        """Duplicate timestamps cause warning."""
        df = pd.DataFrame(
            {
                "ts": [1000, 1000, 3000],  # Duplicate
                "close": [1, 2, 3],
            }
        )

        validator = TimestampValidator()
        result = validator.validate(df)

        assert result.is_valid is True  # Warning only
        assert any("duplicate" in w.lower() for w in result.warnings)
        assert result.details["duplicate_count"] == 1

    def test_non_monotonic_timestamps(self):
        """Non-monotonic timestamps cause warning."""
        df = pd.DataFrame(
            {
                "ts": [3000, 1000, 2000],  # Not increasing
                "close": [1, 2, 3],
            }
        )

        validator = TimestampValidator()
        result = validator.validate(df)

        assert result.is_valid is True  # Warning only
        assert any("monotonic" in w.lower() for w in result.warnings)

    def test_timestamp_column_alternative(self):
        """'timestamp' column is also accepted."""
        df = pd.DataFrame(
            {
                "timestamp": [1000, 2000, 3000],
                "close": [1, 2, 3],
            }
        )

        validator = TimestampValidator()
        result = validator.validate(df)

        assert result.details["timestamp_column"] == "timestamp"


class TestNaNRatioValidator:
    """Tests for NaNRatioValidator."""

    def test_no_indicator_columns(self, ohlcv_basic):
        """DataFrame with only OHLCV columns passes."""
        validator = NaNRatioValidator()
        result = validator.validate(ohlcv_basic)

        assert result.is_valid is True

    def test_low_nan_ratio(self):
        """Low NaN ratio passes."""
        df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [104, 105, 106],
                "volume": [1000, 1100, 1200],
                "rsi_14": [50.0, 60.0, 70.0],
                "ema_21": [100.0, 101.0, 102.0],
            }
        )

        validator = NaNRatioValidator(max_nan_ratio=0.3)
        result = validator.validate(df)

        assert result.is_valid is True

    def test_high_nan_ratio_warning(self):
        """High NaN ratio causes warning."""
        df = pd.DataFrame(
            {
                "open": [100, 101, 102, 103, 104],
                "high": [105, 106, 107, 108, 109],
                "low": [99, 100, 101, 102, 103],
                "close": [104, 105, 106, 107, 108],
                "volume": [1000, 1100, 1200, 1300, 1400],
                "rsi_14": [np.nan, np.nan, np.nan, 60.0, 70.0],  # 60% NaN
            }
        )

        validator = NaNRatioValidator(max_nan_ratio=0.3)
        result = validator.validate(df)

        assert result.is_valid is True  # Warning only
        assert len(result.warnings) > 0

    def test_custom_threshold(self):
        """Custom max_nan_ratio is respected."""
        df = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "indicator": [np.nan, 60.0, 70.0, 80.0, 90.0],  # 20% NaN
            }
        )

        validator = NaNRatioValidator(max_nan_ratio=0.1)  # 10% threshold
        result = validator.validate(df)

        assert len(result.warnings) > 0


class TestValidationChain:
    """Tests for ValidationChain."""

    def test_empty_chain_is_valid(self, ohlcv_with_ts):
        """Empty chain returns valid result."""
        chain = ValidationChain()
        result = chain.validate(ohlcv_with_ts)

        assert result.is_valid is True

    def test_add_validator(self):
        """add() adds validator to chain."""
        chain = ValidationChain()
        chain.add(OHLCVValidator())

        assert len(chain) == 1

    def test_fluent_add(self):
        """add() returns chain for fluent interface."""
        chain = ValidationChain().add(OHLCVValidator()).add(MinRowsValidator())

        assert len(chain) == 2

    def test_remove_validator(self):
        """remove() removes validator by name."""
        chain = ValidationChain().add(OHLCVValidator()).add(MinRowsValidator())

        chain.remove("min_rows")

        assert len(chain) == 1

    def test_clear(self):
        """clear() removes all validators."""
        chain = ValidationChain().add(OHLCVValidator()).add(MinRowsValidator())

        chain.clear()

        assert len(chain) == 0

    def test_chain_runs_all_validators(self, ohlcv_50_bars):
        """Chain runs all validators in sequence."""
        chain = (
            ValidationChain()
            .add(OHLCVValidator())
            .add(MinRowsValidator(min_rows=20))
            .add(TimestampValidator())
        )

        result = chain.validate(ohlcv_50_bars)

        assert result.is_valid is True

    def test_chain_stops_on_critical_failure(self, empty_df):
        """Chain stops when should_stop_on_failure validator fails."""
        validators_run = []

        class TrackingValidator(Validator):
            @property
            def name(self):
                return "tracking"

            def validate(self, df, **kwargs):
                validators_run.append("tracking")
                return ValidationResult()

        chain = (
            ValidationChain()
            .add(OHLCVValidator())  # Fails on empty, stops chain
            .add(TrackingValidator())  # Should not run
        )

        result = chain.validate(empty_df)

        assert result.is_valid is False
        assert "tracking" not in validators_run

    def test_chain_continues_on_non_critical(self):
        """Chain continues after non-critical failures."""
        df = pd.DataFrame(
            {
                "ts": [3000, 1000, 2000],  # Non-monotonic - warning only
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [104, 105, 106],
                "volume": [1000, 1100, 1200],
            }
        )

        validators_run = []

        class TrackingValidator(Validator):
            @property
            def name(self):
                return "tracking"

            def validate(self, df, **kwargs):
                validators_run.append("tracking")
                return ValidationResult()

        chain = (
            ValidationChain()
            .add(TimestampValidator())  # Warns but doesn't stop
            .add(TrackingValidator())  # Should run
        )

        chain.validate(df)

        assert "tracking" in validators_run

    def test_chain_combines_results(self, ohlcv_50_bars):
        """Chain combines results from all validators."""
        chain = (
            ValidationChain().add(OHLCVValidator()).add(MinRowsValidator(min_rows=20))
        )

        result = chain.validate(ohlcv_50_bars)

        # Both validators add details
        assert "row_count" in result.details

    def test_iteration(self):
        """Chain supports iteration."""
        chain = ValidationChain().add(OHLCVValidator()).add(MinRowsValidator())

        names = [v.name for v in chain]

        assert "ohlcv" in names
        assert "min_rows" in names


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_default_chain(self, ohlcv_50_bars):
        """create_default_chain creates chain with standard validators."""
        chain = create_default_chain()

        assert len(chain) == 3  # OHLCV, MinRows, Timestamp

        result = chain.validate(ohlcv_50_bars)
        assert result.is_valid is True

    def test_create_strict_chain(self, ohlcv_50_bars):
        """create_strict_chain creates chain with strict validators."""
        chain = create_strict_chain()

        assert len(chain) == 4  # + NaNRatio

        result = chain.validate(ohlcv_50_bars)
        assert result.is_valid is True

    def test_strict_chain_min_rows(self):
        """Strict chain requires more rows."""
        chain = create_strict_chain()

        df = pd.DataFrame(
            {
                "ts": list(range(30)),
                "open": [100] * 30,
                "high": [105] * 30,
                "low": [99] * 30,
                "close": [104] * 30,
                "volume": [1000] * 30,
            }
        )

        result = chain.validate(df)

        assert result.is_valid is False  # Needs 50+ rows
