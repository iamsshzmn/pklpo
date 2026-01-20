"""
Data validation module for features calculation and saving.

This module provides comprehensive validation functions to ensure data quality
before calculation and database operations.
"""

from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from .logging_config import get_features_logger

logger = get_features_logger("features.validation")


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class DataValidator:
    """Comprehensive data validator for features module."""

    def __init__(self):
        self.logger = get_features_logger("features.validation")
        self.critical_features = ["hlc3", "ema_8", "sma_20"]
        self.required_ohlcv_cols = ["open", "high", "low", "close", "volume"]

    def validate_ohlcv_data(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Validate OHLCV DataFrame before calculation.

        Args:
            df: OHLCV DataFrame

        Returns:
            Validation result
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        try:
            # Check if DataFrame is empty
            if df is None or len(df) == 0:
                result["errors"].append("DataFrame is empty or None")
                result["valid"] = False
                return result

            # Check required columns
            missing_cols = [
                col for col in self.required_ohlcv_cols if col not in df.columns
            ]
            if missing_cols:
                result["errors"].append(f"Missing required columns: {missing_cols}")
                result["valid"] = False

            # Check minimum rows
            if len(df) < 20:
                result["warnings"].append(
                    f"Low row count: {len(df)} (minimum recommended: 20)"
                )

            # Check for negative values in OHLCV
            ohlcv_negative_check = self._check_negative_values(df)
            if not ohlcv_negative_check["valid"]:
                result["errors"].extend(ohlcv_negative_check["errors"])
                result["valid"] = False

            # Validate OHLCV data quality
            for col in self.required_ohlcv_cols:
                if col in df.columns:
                    col_result = self._validate_numeric_column(df[col], col)
                    result["errors"].extend(col_result["errors"])
                    result["warnings"].extend(col_result["warnings"])

            # Check for timestamp column
            if "ts" in df.columns:
                ts_result = self._validate_timestamp_column(df["ts"])
                result["errors"].extend(ts_result["errors"])
                result["warnings"].extend(ts_result["warnings"])
            else:
                result["warnings"].append("No timestamp column found")

            # Calculate statistics
            result["stats"] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "null_counts": df.isnull().sum().to_dict(),
                "dtypes": df.dtypes.to_dict(),
            }

            # Check for duplicate timestamps
            if "ts" in df.columns:
                duplicate_ts = df["ts"].duplicated().sum()
                if duplicate_ts > 0:
                    result["warnings"].append(
                        f"Found {duplicate_ts} duplicate timestamps"
                    )

            return result

        except Exception as e:
            result["errors"].append(f"Validation error: {e!s}")
            result["valid"] = False
            return result

    def validate_calculated_features(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Validate calculated features DataFrame.

        Args:
            df: DataFrame with calculated features

        Returns:
            Validation result
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        try:
            if df is None or len(df) == 0:
                result["errors"].append("Features DataFrame is empty")
                result["valid"] = False
                return result

            # Check for critical features
            missing_critical = [
                f for f in self.critical_features if f not in df.columns
            ]
            if missing_critical:
                result["warnings"].append(
                    f"Missing critical features: {missing_critical}"
                )

            # Check feature quality
            feature_cols = [
                col
                for col in df.columns
                if col not in [*self.required_ohlcv_cols, "ts"]
            ]

            if not feature_cols:
                result["warnings"].append("No feature columns found")

            # Calculate fill rates
            fill_rates = {}
            for col in feature_cols:
                non_null_count = df[col].notna().sum()
                fill_rate = (non_null_count / len(df) * 100) if len(df) > 0 else 0
                fill_rates[col] = fill_rate

                # Warn about low fill rates
                if fill_rate < 50:
                    result["warnings"].append(
                        f"Low fill rate for {col}: {fill_rate:.1f}%"
                    )

            # Check for infinite values
            inf_counts = {}
            for col in feature_cols:
                inf_count = np.isinf(df[col]).sum()
                if inf_count > 0:
                    inf_counts[col] = inf_count
                    result["warnings"].append(f"Infinite values in {col}: {inf_count}")

            result["stats"] = {
                "row_count": len(df),
                "feature_count": len(feature_cols),
                "fill_rates": fill_rates,
                "inf_counts": inf_counts,
                "critical_features_present": len(
                    [f for f in self.critical_features if f in df.columns]
                ),
            }

            return result

        except Exception as e:
            result["errors"].append(f"Feature validation error: {e!s}")
            result["valid"] = False
            return result

    def validate_database_data(
        self, batch_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Validate data before database insertion.

        Args:
            batch_data: List of dictionaries for database insertion

        Returns:
            Validation result
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        try:
            if not batch_data:
                result["errors"].append("No data to validate")
                result["valid"] = False
                return result

            # Check required fields
            required_fields = ["symbol", "timeframe", "timestamp"]
            for i, record in enumerate(batch_data):
                missing_fields = [f for f in required_fields if f not in record]
                if missing_fields:
                    result["errors"].append(
                        f"Record {i}: Missing required fields: {missing_fields}"
                    )
                    result["valid"] = False

                # Validate timestamp
                if "timestamp" in record:
                    ts = record["timestamp"]
                    if not isinstance(ts, int | float) or pd.isna(ts):
                        result["errors"].append(f"Record {i}: Invalid timestamp: {ts}")
                        result["valid"] = False
                    elif ts <= 0:
                        result["warnings"].append(
                            f"Record {i}: Non-positive timestamp: {ts}"
                        )

                # Validate indicator values
                indicator_count = 0
                for key, value in record.items():
                    if key not in [*required_fields, "calculated_at"]:
                        if pd.isna(value) or value is None:
                            continue
                        try:
                            float(value)
                            indicator_count += 1
                        except (ValueError, TypeError):
                            result["warnings"].append(
                                f"Record {i}: Invalid indicator value {key}={value}"
                            )

                if indicator_count == 0:
                    result["warnings"].append(f"Record {i}: No valid indicators")

            result["stats"] = {
                "record_count": len(batch_data),
                "avg_indicators_per_record": sum(
                    len([k for k in r if k not in [*required_fields, "calculated_at"]])
                    for r in batch_data
                )
                / len(batch_data),
            }

            return result

        except Exception as e:
            result["errors"].append(f"Database validation error: {e!s}")
            result["valid"] = False
            return result

    def _check_negative_values(self, df: pd.DataFrame) -> dict[str, Any]:
        """Check for negative values in OHLCV columns."""
        result: dict[str, Any] = {"valid": True, "errors": []}

        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    result["errors"].append(
                        f"{col}: Found {negative_count} negative values"
                    )
                    result["valid"] = False

        return result

    def _validate_numeric_column(
        self, series: pd.Series, col_name: str
    ) -> dict[str, list[str]]:
        """Validate a numeric column."""
        result: dict[str, list[str]] = {"errors": [], "warnings": []}

        # Check for non-numeric values
        try:
            numeric_series = pd.to_numeric(series, errors="coerce")
            non_numeric_count = numeric_series.isna().sum() - series.isna().sum()
            if non_numeric_count > 0:
                result["warnings"].append(
                    f"{col_name}: {non_numeric_count} non-numeric values"
                )
        except Exception:
            result["errors"].append(f"{col_name}: Cannot convert to numeric")

        # Check for negative values in price columns - это критичная ошибка
        if col_name in ["open", "high", "low", "close"]:
            negative_count = (series < 0).sum()
            if negative_count > 0:
                result["errors"].append(
                    f"{col_name}: Found {negative_count} negative values - "
                    f"prices cannot be negative"
                )

        # Check for zero values in price columns
        if col_name in ["open", "high", "low", "close"]:
            zero_count = (series == 0).sum()
            if zero_count > 0:
                result["warnings"].append(f"{col_name}: {zero_count} zero values")

        # Check for infinite values
        inf_count = np.isinf(series).sum()
        if inf_count > 0:
            result["errors"].append(f"{col_name}: {inf_count} infinite values")

        return result

    def _validate_timestamp_column(self, series: pd.Series) -> dict[str, list[str]]:
        """Validate timestamp column."""
        result: dict[str, list[str]] = {"errors": [], "warnings": []}

        # Check for NaN values
        nan_count = series.isna().sum()
        if nan_count > 0:
            result["errors"].append(f"Timestamp: {nan_count} NaN values")

        # Check timestamp range
        if not series.empty:
            series.min()
            series.max()
            current_ts = datetime.now(UTC).timestamp()

            # Check for future timestamps
            future_count = (
                series > current_ts + 86400
            ).sum()  # More than 1 day in future
            if future_count > 0:
                result["warnings"].append(
                    f"Timestamp: {future_count} future timestamps"
                )

            # Check for very old timestamps
            old_count = (
                series < current_ts - 365 * 24 * 3600
            ).sum()  # Older than 1 year
            if old_count > 0:
                result["warnings"].append(f"Timestamp: {old_count} very old timestamps")

        return result


def validate_data_quality(
    df: pd.DataFrame, data_type: str = "ohlcv", strict: bool = False
) -> tuple[bool, dict[str, Any]]:
    """
    Main validation function for data quality.

    Args:
        df: DataFrame to validate
        data_type: Type of data ("ohlcv", "features", "database")
        strict: Whether to use strict validation

    Returns:
        Tuple of (is_valid, validation_result)
    """
    validator = DataValidator()

    if data_type == "ohlcv":
        result = validator.validate_ohlcv_data(df)
    elif data_type == "features":
        result = validator.validate_calculated_features(df)
    else:
        raise ValueError(f"Unknown data type: {data_type}")

    # Apply strict validation if requested
    if strict and result["warnings"]:
        result["errors"].extend(result["warnings"])
        result["warnings"] = []
        result["valid"] = len(result["errors"]) == 0

    return result["valid"], result


def check_data_consistency(df: pd.DataFrame) -> dict[str, Any]:
    """
    Check data consistency and quality metrics.

    Args:
        df: DataFrame to check

    Returns:
        Consistency report
    """
    report: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "row_count": len(df),
        "column_count": len(df.columns),
        "issues": [],
        "quality_score": 0.0,
    }

    try:
        # Check for duplicate rows
        duplicate_count = df.duplicated().sum()
        if duplicate_count > 0:
            report["issues"].append(f"Duplicate rows: {duplicate_count}")

        # Check for missing values
        null_counts = df.isnull().sum()
        total_nulls = null_counts.sum()
        null_percentage = (
            (total_nulls / (len(df) * len(df.columns)) * 100) if len(df) > 0 else 0
        )

        if null_percentage > 10:
            report["issues"].append(f"High null percentage: {null_percentage:.1f}%")

        # Check for constant columns
        constant_cols = [col for col in df.columns if df[col].nunique() <= 1]
        if constant_cols:
            report["issues"].append(f"Constant columns: {constant_cols}")

        # Calculate quality score
        quality_factors = [
            1.0 if duplicate_count == 0 else 0.8,
            1.0 if null_percentage < 5 else 0.9 if null_percentage < 10 else 0.7,
            1.0 if len(constant_cols) == 0 else 0.9,
        ]

        report["quality_score"] = sum(quality_factors) / len(quality_factors)

        return report

    except Exception as e:
        report["issues"].append(f"Consistency check error: {e!s}")
        report["quality_score"] = 0.0
        return report


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.append(str(Path(__file__).parent.parent.parent))

    parser = argparse.ArgumentParser(description="Validate data quality")
    parser.add_argument("input_file", help="Input CSV or parquet file")
    parser.add_argument(
        "--data-type",
        choices=["ohlcv", "features"],
        default="ohlcv",
        help="Type of data to validate",
    )
    parser.add_argument("--strict", action="store_true", help="Use strict validation")

    args = parser.parse_args()

    try:
        # Load data
        if args.input_file.endswith(".parquet"):
            df = pd.read_parquet(args.input_file)
        else:
            df = pd.read_csv(args.input_file)

        # Validate
        is_valid, result = validate_data_quality(df, args.data_type, args.strict)

        print(f"Validation result: {'✅ VALID' if is_valid else '❌ INVALID'}")
        print(f"Errors: {len(result['errors'])}")
        print(f"Warnings: {len(result['warnings'])}")

        if result["errors"]:
            print("\nErrors:")
            for error in result["errors"]:
                print(f"  - {error}")

        if result["warnings"]:
            print("\nWarnings:")
            for warning in result["warnings"]:
                print(f"  - {warning}")

        # Consistency check
        consistency = check_data_consistency(df)
        print(f"\nQuality score: {consistency['quality_score']:.2f}")

        if consistency["issues"]:
            print("Issues found:")
            for issue in consistency["issues"]:
                print(f"  - {issue}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
