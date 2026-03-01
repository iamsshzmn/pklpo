"""
Additional code validations as specified in the plan.

This module implements additional validations:
- fraction_outliers по цене/объему
- окно "прогрева" для длинных MA/ATR
"""

from typing import Any

import pandas as pd

from ..observability.logging import get_features_logger

logger = get_features_logger("features.code_validations")


class ValidationConfig:
    """Configuration for additional validations."""

    def __init__(self):
        # Outlier detection settings
        self.price_outlier_threshold = 0.02  # 2% outliers max (more strict)
        self.volume_outlier_threshold = 0.02  # 2% outliers max (more strict)
        self.outlier_method = "iqr"  # "iqr" or "zscore"
        self.outlier_multiplier = 1.5  # IQR multiplier or z-score threshold

        # Warm-up window settings
        self.ma_warmup_multiplier = 2.0  # Warm-up = period * multiplier
        self.atr_warmup_multiplier = 2.0  # Warm-up = period * multiplier
        self.min_warmup_rows = 50  # Minimum warm-up rows

        # Price validation settings
        self.min_price_change = 0.001  # 0.1% minimum price change
        self.max_price_change = 0.5  # 50% maximum price change
        self.min_volume = 1  # Minimum volume


class CodeValidator:
    """Additional code validations for features calculation."""

    def __init__(self, config: ValidationConfig | None = None):
        self.config = config or ValidationConfig()
        self.logger = get_features_logger("features.code_validations")

    def validate_price_outliers(self, df: pd.DataFrame) -> tuple[bool, dict[str, Any]]:
        """
        Validate fraction of outliers in price data.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple (is_valid, validation_result)
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        price_columns = ["open", "high", "low", "close"]
        existing_price_cols = [col for col in price_columns if col in df.columns]

        if not existing_price_cols:
            result["warnings"].append("No price columns found for outlier validation")
            return True, result

        total_outliers = 0
        total_values = 0

        for col in existing_price_cols:
            series = df[col].dropna()
            if len(series) < 2:
                continue

            # Detect outliers using IQR method
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1

            if IQR > 0:
                lower_bound = Q1 - self.config.outlier_multiplier * IQR
                upper_bound = Q3 + self.config.outlier_multiplier * IQR

                outliers = series[(series < lower_bound) | (series > upper_bound)]
                outlier_count = len(outliers)

                total_outliers += outlier_count
                total_values += len(series)

                outlier_fraction = outlier_count / len(series)
                result["stats"][f"{col}_outlier_fraction"] = outlier_fraction

                if outlier_fraction > self.config.price_outlier_threshold:
                    result["valid"] = False
                    result["errors"].append(
                        f"High outlier fraction in {col}: {outlier_fraction:.2%} > {self.config.price_outlier_threshold:.2%}"
                    )

        if total_values > 0:
            overall_outlier_fraction = total_outliers / total_values
            result["stats"]["overall_price_outlier_fraction"] = overall_outlier_fraction

            if overall_outlier_fraction > self.config.price_outlier_threshold:
                result["valid"] = False
                result["errors"].append(
                    f"High overall price outlier fraction: {overall_outlier_fraction:.2%} > {self.config.price_outlier_threshold:.2%}"
                )

        return result["valid"], result

    def validate_volume_outliers(self, df: pd.DataFrame) -> tuple[bool, dict[str, Any]]:
        """
        Validate fraction of outliers in volume data.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple (is_valid, validation_result)
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        if "volume" not in df.columns:
            result["warnings"].append("Volume column not found for outlier validation")
            return True, result

        volume_series = df["volume"].dropna()
        if len(volume_series) < 2:
            result["warnings"].append("Insufficient volume data for outlier validation")
            return True, result

        # Detect outliers using IQR method
        Q1 = volume_series.quantile(0.25)
        Q3 = volume_series.quantile(0.75)
        IQR = Q3 - Q1

        if IQR > 0:
            lower_bound = Q1 - self.config.outlier_multiplier * IQR
            upper_bound = Q3 + self.config.outlier_multiplier * IQR

            outliers = volume_series[
                (volume_series < lower_bound) | (volume_series > upper_bound)
            ]
            outlier_count = len(outliers)
            outlier_fraction = outlier_count / len(volume_series)

            result["stats"]["volume_outlier_fraction"] = outlier_fraction

            if outlier_fraction > self.config.volume_outlier_threshold:
                result["valid"] = False
                result["errors"].append(
                    f"High volume outlier fraction: {outlier_fraction:.2%} > {self.config.volume_outlier_threshold:.2%}"
                )

        return result["valid"], result

    def validate_warmup_window(
        self, df: pd.DataFrame, feature_periods: dict[str, int]
    ) -> tuple[bool, dict[str, Any]]:
        """
        Validate warm-up window for long MA/ATR indicators.

        Args:
            df: DataFrame with calculated features
            feature_periods: Dictionary mapping feature names to their periods

        Returns:
            Tuple (is_valid, validation_result)
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        # Don't skip validation for small datasets
        # If any feature requires more rows than available, it should fail

        # Check MA indicators
        ma_features = {
            name: period
            for name, period in feature_periods.items()
            if any(
                prefix in name.lower() for prefix in ["sma_", "ema_", "wma_", "hma_"]
            )
        }

        # Check ATR indicators
        atr_features = {
            name: period
            for name, period in feature_periods.items()
            if "atr_" in name.lower()
        }

        # Validate MA warm-up
        for feature_name, period in ma_features.items():
            if feature_name in df.columns:
                warmup_rows = int(period * self.config.ma_warmup_multiplier)
                warmup_rows = max(warmup_rows, self.config.min_warmup_rows)

                if len(df) < warmup_rows:
                    result["valid"] = False
                    result["errors"].append(
                        f"Insufficient warm-up for {feature_name}: {len(df)} rows < {warmup_rows} required"
                    )
                else:
                    # Check if feature has valid values after warm-up
                    feature_series = df[feature_name].iloc[warmup_rows:]
                    valid_count = feature_series.notna().sum()
                    total_count = len(feature_series)

                    if total_count > 0:
                        valid_fraction = valid_count / total_count
                        result["stats"][f"{feature_name}_warmup_valid_fraction"] = (
                            valid_fraction
                        )

                        if valid_fraction < 0.8:  # 80% valid after warm-up
                            result["warnings"].append(
                                f"Low valid fraction for {feature_name} after warm-up: {valid_fraction:.2%}"
                            )

        # Validate ATR warm-up
        for feature_name, period in atr_features.items():
            if feature_name in df.columns:
                warmup_rows = int(period * self.config.atr_warmup_multiplier)
                warmup_rows = max(warmup_rows, self.config.min_warmup_rows)

                if len(df) < warmup_rows:
                    result["valid"] = False
                    result["errors"].append(
                        f"Insufficient warm-up for {feature_name}: {len(df)} rows < {warmup_rows} required"
                    )
                else:
                    # Check if feature has valid values after warm-up
                    feature_series = df[feature_name].iloc[warmup_rows:]
                    valid_count = feature_series.notna().sum()
                    total_count = len(feature_series)

                    if total_count > 0:
                        valid_fraction = valid_count / total_count
                        result["stats"][f"{feature_name}_warmup_valid_fraction"] = (
                            valid_fraction
                        )

                        if valid_fraction < 0.8:  # 80% valid after warm-up
                            result["warnings"].append(
                                f"Low valid fraction for {feature_name} after warm-up: {valid_fraction:.2%}"
                            )

        return result["valid"], result

    def validate_price_changes(self, df: pd.DataFrame) -> tuple[bool, dict[str, Any]]:
        """
        Validate price changes for reasonable ranges.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Tuple (is_valid, validation_result)
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        if "close" not in df.columns or len(df) < 2:
            result["warnings"].append("Insufficient price data for change validation")
            return True, result

        # Calculate price changes
        price_changes = df["close"].pct_change().dropna()

        if len(price_changes) == 0:
            result["warnings"].append("No price changes calculated")
            return True, result

        # Check for extreme changes
        extreme_changes = price_changes[
            (price_changes.abs() > self.config.max_price_change)
            | (price_changes.abs() < self.config.min_price_change)
        ]

        extreme_fraction = len(extreme_changes) / len(price_changes)
        result["stats"]["extreme_price_change_fraction"] = extreme_fraction

        if extreme_fraction > 0.1:  # 10% extreme changes
            result["warnings"].append(
                f"High fraction of extreme price changes: {extreme_fraction:.2%}"
            )

        # Check for zero volume
        if "volume" in df.columns:
            zero_volume_count = (df["volume"] <= 0).sum()
            zero_volume_fraction = zero_volume_count / len(df)
            result["stats"]["zero_volume_fraction"] = zero_volume_fraction

            if zero_volume_fraction > 0.05:  # 5% zero volume
                result["warnings"].append(
                    f"High fraction of zero volume: {zero_volume_fraction:.2%}"
                )

        return result["valid"], result

    def validate_all(
        self, df: pd.DataFrame, feature_periods: dict[str, int] | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """
        Run all additional validations.

        Args:
            df: DataFrame with OHLCV data and calculated features
            feature_periods: Dictionary mapping feature names to their periods

        Returns:
            Tuple (is_valid, validation_result)
        """
        if feature_periods is None:
            feature_periods = {}

        all_valid = True
        all_results: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        # Run all validations
        validations = [
            self.validate_price_outliers,
            self.validate_volume_outliers,
            self.validate_price_changes,
        ]

        for validation_func in validations:
            try:
                is_valid, result = validation_func(df)
                if not is_valid:
                    all_valid = False

                result_dict: dict[str, Any] = result
                all_results["errors"].extend(result_dict["errors"])
                all_results["warnings"].extend(result_dict["warnings"])
                all_results["stats"].update(result_dict["stats"])

            except Exception as e:
                self.logger.error(
                    f"Validation error in {validation_func.__name__}: {e}"
                )
                all_results["errors"].append(
                    f"Validation error in {validation_func.__name__}: {e}"
                )
                all_valid = False

        # Run warm-up validation if feature periods provided
        if feature_periods:
            try:
                is_valid, warmup_result = self.validate_warmup_window(
                    df, feature_periods
                )
                if not is_valid:
                    all_valid = False

                warmup_result_dict: dict[str, Any] = warmup_result
                all_results["errors"].extend(warmup_result_dict["errors"])
                all_results["warnings"].extend(warmup_result_dict["warnings"])
                all_results["stats"].update(warmup_result_dict["stats"])

            except Exception as e:
                self.logger.error(f"Warm-up validation error: {e}")
                all_results["errors"].append(f"Warm-up validation error: {e}")
                all_valid = False

        all_results["valid"] = all_valid

        if not all_valid:
            self.logger.error(f"Additional validations failed: {all_results['errors']}")
        elif all_results["warnings"]:
            self.logger.warning(
                f"Additional validations passed with warnings: {all_results['warnings']}"
            )
        else:
            self.logger.info("All additional validations passed")

        return all_valid, all_results


def create_code_validator(config: ValidationConfig | None = None) -> CodeValidator:
    """
    Create a code validator instance.

    Args:
        config: Configuration for validations

    Returns:
        CodeValidator instance
    """
    return CodeValidator(config)
