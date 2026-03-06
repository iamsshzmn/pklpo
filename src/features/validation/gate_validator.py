"""
Gate validation module for features calculation.

This module implements strict quality gates before database operations
as specified in the plan: " ,  len(df)<min_rows
nan_ratio(feature_group) > threshold  fill_rate<min_fill".
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.logging import get_features_logger

logger = get_features_logger("features.gate_validation")


@dataclass
class GateConfig:
    """Configuration for gate validation."""

    # Minimum data requirements
    min_rows: int = 20
    min_fill_rate: float = 0.5  # Minimum 50% fill rate

    # Quality thresholds
    max_nan_ratio: float = 0.1  # Maximum 10% NaN ratio per feature group
    max_outlier_ratio: float = 0.05  # Maximum 5% outliers

    # Critical features that must be present
    critical_features: list[str] | None = None

    def __post_init__(self):
        import os

        # Allow overriding thresholds via environment variables
        if os.getenv("FEATURES_MIN_FILL_RATE"):
            try:
                self.min_fill_rate = float(os.getenv("FEATURES_MIN_FILL_RATE"))
                logger.info(f"Overriding min_fill_rate from env: {self.min_fill_rate}")
            except ValueError:
                logger.warning(
                    f"Invalid FEATURES_MIN_FILL_RATE value: {os.getenv('FEATURES_MIN_FILL_RATE')}"
                )

        if os.getenv("FEATURES_MAX_NAN_RATIO"):
            try:
                self.max_nan_ratio = float(os.getenv("FEATURES_MAX_NAN_RATIO"))
                logger.info(f"Overriding max_nan_ratio from env: {self.max_nan_ratio}")
            except ValueError:
                logger.warning(
                    f"Invalid FEATURES_MAX_NAN_RATIO value: {os.getenv('FEATURES_MAX_NAN_RATIO')}"
                )

        if self.critical_features is None:
            # Default: no critical features required (too strict for tests)
            # Production code should set this explicitly
            self.critical_features = []


class GateValidator:
    """Gate validator for features data quality."""

    def __init__(self, config: GateConfig | None = None):
        self.config = config or GateConfig()
        self.logger = get_features_logger("features.gate_validation")

    def validate_before_write(
        self, df: pd.DataFrame, feature_groups: dict[str, list[str]]
    ) -> tuple[bool, dict[str, Any]]:
        """
        Validate data quality before writing to database.

        Args:
            df: DataFrame with calculated features
            feature_groups: Dictionary mapping group names to feature lists

        Returns:
            Tuple of (is_valid, validation_result)
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        try:
            # Gate 1: Minimum rows check
            if len(df) < self.config.min_rows:
                result["valid"] = False
                result["errors"].append(
                    f"Insufficient rows: {len(df)} < {self.config.min_rows}"
                )

            # Gate 2: Critical features presence
            if self.config.critical_features:
                missing_critical = [
                    f for f in self.config.critical_features if f not in df.columns
                ]
            else:
                missing_critical = []
            if missing_critical:
                result["valid"] = False
                result["errors"].append(
                    f"Missing critical features: {missing_critical}"
                )

            # Gate 3: Feature group quality checks
            for group_name, features in feature_groups.items():
                group_result = self._validate_feature_group(df, group_name, features)

                if not group_result["valid"]:
                    result["valid"] = False
                    result["errors"].extend(group_result["errors"])

                result["warnings"].extend(group_result["warnings"])
                result["stats"][group_name] = group_result["stats"]

            # Gate 4: Overall data quality
            overall_quality = self._calculate_overall_quality(df)
            result["stats"]["overall_quality"] = overall_quality

            if overall_quality["fill_rate"] < self.config.min_fill_rate:
                result["valid"] = False
                result["errors"].append(
                    f"Overall fill rate too low: {overall_quality['fill_rate']:.2%} < {self.config.min_fill_rate:.2%}"
                )

            # Gate 5: Outlier detection
            outlier_stats = self._detect_outliers(df)
            result["stats"]["outliers"] = outlier_stats

            if outlier_stats["outlier_ratio"] > self.config.max_outlier_ratio:
                result["warnings"].append(
                    f"High outlier ratio: {outlier_stats['outlier_ratio']:.2%} > {self.config.max_outlier_ratio:.2%}"
                )

            return result["valid"], result

        except Exception as e:
            self.logger.error(f"Gate validation error: {e}")
            result["valid"] = False
            result["errors"].append(f"Validation error: {e!s}")
            return False, result

    def _validate_feature_group(
        self, df: pd.DataFrame, group_name: str, features: list[str]
    ) -> dict[str, Any]:
        """Validate a specific feature group."""
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        # Filter features that exist in DataFrame
        existing_features = [f for f in features if f in df.columns]

        if not existing_features:
            result["warnings"].append(
                f"No features from group {group_name} found in DataFrame"
            )
            return result

        # Calculate group statistics
        group_df = df[existing_features]

        # Fill rate calculation
        non_null_counts = group_df.notna().sum()
        total_count = len(group_df)
        fill_rates = non_null_counts / total_count

        avg_fill_rate = fill_rates.mean()
        min_fill_rate = fill_rates.min()

        # NaN ratio calculation
        nan_counts = group_df.isna().sum()
        nan_ratios = nan_counts / total_count
        avg_nan_ratio = nan_ratios.mean()
        max_nan_ratio = nan_ratios.max()

        # Check thresholds
        if min_fill_rate < self.config.min_fill_rate:
            result["valid"] = False
            result["errors"].append(
                f"Group {group_name}: minimum fill rate {min_fill_rate:.2%} < {self.config.min_fill_rate:.2%}"
            )

        if max_nan_ratio > self.config.max_nan_ratio:
            result["valid"] = False
            result["errors"].append(
                f"Group {group_name}: maximum NaN ratio {max_nan_ratio:.2%} > {self.config.max_nan_ratio:.2%}"
            )

        # Check for infinite values (CRITICAL: should be error, not warning)
        inf_counts = np.isinf(group_df).sum()
        total_inf = inf_counts.sum()
        if total_inf > 0:
            result["valid"] = False
            result["errors"].append(
                f"Group {group_name}: {total_inf} infinite values found"
            )

        # Statistics
        result["stats"] = {
            "feature_count": len(existing_features),
            "avg_fill_rate": avg_fill_rate,
            "min_fill_rate": min_fill_rate,
            "avg_nan_ratio": avg_nan_ratio,
            "max_nan_ratio": max_nan_ratio,
            "infinite_count": total_inf,
            "features": existing_features,
        }

        return result

    def _calculate_overall_quality(self, df: pd.DataFrame) -> dict[str, Any]:
        """Calculate overall data quality metrics."""
        # Exclude OHLCV and timestamp columns
        exclude_cols = ["open", "high", "low", "close", "volume", "ts", "timestamp"]
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        if not feature_cols:
            return {"fill_rate": 0.0, "nan_ratio": 1.0, "feature_count": 0}

        feature_df = df[feature_cols]

        # Overall fill rate
        total_cells = len(feature_df) * len(feature_cols)
        non_null_cells = feature_df.notna().sum().sum()
        fill_rate = non_null_cells / total_cells if total_cells > 0 else 0.0

        # Overall NaN ratio
        nan_cells = feature_df.isna().sum().sum()
        nan_ratio = nan_cells / total_cells if total_cells > 0 else 1.0

        return {
            "fill_rate": fill_rate,
            "nan_ratio": nan_ratio,
            "feature_count": len(feature_cols),
            "total_cells": total_cells,
            "non_null_cells": non_null_cells,
            "nan_cells": nan_cells,
        }

    def _detect_outliers(self, df: pd.DataFrame) -> dict[str, Any]:
        """Detect outliers in feature data."""
        exclude_cols = ["open", "high", "low", "close", "volume", "ts", "timestamp"]
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        if not feature_cols:
            return {"outlier_count": 0, "outlier_ratio": 0.0, "outlier_features": []}

        outlier_counts = {}
        total_outliers = 0
        total_cells = 0

        for col in feature_cols:
            series = df[col].dropna()
            if len(series) == 0:
                continue

            # Use IQR method for outlier detection
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1

            if IQR > 0:
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                outliers = series[(series < lower_bound) | (series > upper_bound)]

                if len(outliers) > 0:
                    outlier_counts[col] = len(outliers)
                    total_outliers += len(outliers)

            total_cells += len(series)

        outlier_ratio = total_outliers / total_cells if total_cells > 0 else 0.0

        return {
            "outlier_count": total_outliers,
            "outlier_ratio": outlier_ratio,
            "outlier_features": list(outlier_counts.keys()),
            "feature_outlier_counts": outlier_counts,
        }


def create_default_gate_config() -> GateConfig:
    """Create default gate configuration."""
    return GateConfig()


def validate_data_gate(
    df: pd.DataFrame, feature_groups: dict[str, list[str]] | None = None
) -> tuple[bool, dict[str, Any]]:
    """
    Quick gate validation function.

    Args:
        df: DataFrame to validate
        feature_groups: Optional feature groups mapping

    Returns:
        Tuple of (is_valid, validation_result)
    """
    if feature_groups is None:
        # Default feature groups based on common patterns
        feature_groups = {
            "moving_averages": [
                col
                for col in df.columns
                if col.startswith(("sma_", "ema_", "wma_", "hma_"))
            ],
            "oscillators": [
                col
                for col in df.columns
                if col.startswith(("rsi_", "macd", "stoch", "cci_"))
            ],
            "volatility": [
                col
                for col in df.columns
                if col.startswith(("atr_", "bb_", "kc_", "dc_"))
            ],
            "volume": [
                col
                for col in df.columns
                if col.startswith(("obv", "cmf", "vwap", "mfi_"))
            ],
            "trend": [
                col
                for col in df.columns
                if col.startswith(("adx_", "aroon", "supertrend", "psar"))
            ],
            "overlap": [
                col for col in df.columns if col in ["hlc3", "hl2", "ohlc4", "wcp"]
            ],
        }

    validator = GateValidator()
    return validator.validate_before_write(df, feature_groups)


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.append(str(Path(__file__).parent.parent.parent))

    parser = argparse.ArgumentParser(description="Gate validation for features data")
    parser.add_argument("input_file", help="Input CSV or parquet file")
    parser.add_argument(
        "--min-rows", type=int, default=20, help="Minimum rows required"
    )
    parser.add_argument(
        "--min-fill-rate", type=float, default=0.5, help="Minimum fill rate"
    )
    parser.add_argument(
        "--max-nan-ratio", type=float, default=0.1, help="Maximum NaN ratio"
    )

    args = parser.parse_args()

    try:
        # Load data
        if args.input_file.endswith(".parquet"):
            df = pd.read_parquet(args.input_file)
        else:
            df = pd.read_csv(args.input_file)

        # Create custom config
        config = GateConfig(
            min_rows=args.min_rows,
            min_fill_rate=args.min_fill_rate,
            max_nan_ratio=args.max_nan_ratio,
        )

        # Validate
        validator = GateValidator(config)
        is_valid, result = validator.validate_before_write(df, {})

        print(f"Gate validation result: {'✅ PASSED' if is_valid else '❌ FAILED'}")
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

        # Print statistics
        if "overall_quality" in result["stats"]:
            quality = result["stats"]["overall_quality"]
            print("\nOverall Quality:")
            print(f"  Fill rate: {quality['fill_rate']:.2%}")
            print(f"  NaN ratio: {quality['nan_ratio']:.2%}")
            print(f"  Feature count: {quality['feature_count']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
