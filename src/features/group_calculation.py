"""
Group-based calculation with batch persistence.

This module implements the group-based calculation architecture as specified in the plan:
overlap → MA → oscillators → volatility → volume → trend → candles → squeeze → statistics → performance

Each group is calculated on a common DataFrame and immediately persisted as a batch.
"""

import time

import pandas as pd

from .logging_config import get_features_logger

# Public API
__all__ = [
    # Configuration
    "GroupCalculationConfig",
    "GroupCalculator",
    # Main calculation function
    "compute_features_grouped",
    # Calculation order (as per plan)
    "CALCULATION_ORDER",
]

# Standard calculation order for all indicator groups
CALCULATION_ORDER = [
    "overlap",  # Basic price calculations (hlc3, hl2, etc) - no dependencies
    "ma",  # Moving averages - depends on OHLC
    "oscillators",  # RSI, MACD, Stochastic - depends on close, MA
    "volatility",  # ATR, Bollinger Bands - depends on OHLC, MA
    "volume",  # OBV, CMF, VWAP - depends on volume
    "trend",  # ADX, Aroon, Supertrend - depends on OHLC, ATR
    "candles",  # Candlestick patterns - depends on OHLC
    "squeeze",  # Squeeze Momentum - depends on BB, KC
    "statistics",  # Statistical measures - depends on price data
    "performance",  # Performance metrics - depends on close
]
from .code_validations import CodeValidator, ValidationConfig
from .gate_validation import validate_data_gate
from .metrics import (
    calculate_fill_rates,
    calculate_quality_score,
    finish_calculation_metrics,
    record_fill_rate,
    record_quality_metrics,
    start_calculation_metrics,
)
from .models import FeatureError
from .time_utils import ensure_ts_column, strict_timestamp_validation
from .upsert_optimizer import UpsertConfig, UpsertOptimizer

logger = get_features_logger("features.group_calculation")


class GroupCalculationConfig:
    """Configuration for group-based calculation."""

    def __init__(self):
        # Calculation order as per plan (use module-level constant)
        self.calculation_order = CALCULATION_ORDER

        # Batch persistence settings
        self.batch_size = 5000  # 5k-10k rows as per plan
        self.max_retries = 3
        self.retry_delay_base = 1.0  # Base delay for exponential backoff

        # Quality gates
        self.min_rows = 20
        self.min_fill_rate = 0.5
        self.max_nan_ratio = 0.1


class GroupCalculator:
    """Calculator for group-based feature calculation with batch persistence."""

    def __init__(self, config: GroupCalculationConfig | None = None):
        self.config = config or GroupCalculationConfig()
        self.logger = get_features_logger("features.group_calculation")

        # Initialize UPSERT optimizer
        self.upsert_optimizer = UpsertOptimizer(UpsertConfig())

        # Initialize code validator
        self.code_validator = CodeValidator(ValidationConfig())

        # Import group calculation functions
        self._import_group_functions()

    def _import_group_functions(self):
        """Import calculation functions for each group."""
        try:
            from .indicator_groups.candles import calc_candle_indicators
            from .indicator_groups.ma import calc_ma_indicators
            from .indicator_groups.oscillators import calc_oscillator_indicators
            from .indicator_groups.overlap import calc_overlap_indicators
            from .indicator_groups.performance import calc_performance_indicators
            from .indicator_groups.squeeze import calc_squeeze_indicators
            from .indicator_groups.statistics import calc_statistics_indicators
            from .indicator_groups.trend import calc_trend_indicators
            from .indicator_groups.volatility import calc_volatility_indicators
            from .indicator_groups.volume import calc_volume_indicators

            self.group_functions = {
                "overlap": calc_overlap_indicators,
                "ma": calc_ma_indicators,
                "oscillators": calc_oscillator_indicators,
                "volatility": calc_volatility_indicators,
                "volume": calc_volume_indicators,
                "trend": calc_trend_indicators,
                "candles": calc_candle_indicators,
                "squeeze": calc_squeeze_indicators,
                "statistics": calc_statistics_indicators,
                "performance": calc_performance_indicators,
            }

            self.logger.info(
                f"Imported {len(self.group_functions)} group calculation functions"
            )

        except ImportError as e:
            self.logger.error(f"Failed to import group functions: {e}")
            raise FeatureError(
                f"Failed to import group calculation functions: {e}"
            ) from e

    def calculate_group(
        self, df: pd.DataFrame, group_name: str, **kwargs
    ) -> pd.DataFrame:
        """
        Calculate features for a specific group.

        Args:
            df: DataFrame with OHLCV data and previously calculated features
            group_name: Name of the group to calculate
            **kwargs: Additional parameters for calculation

        Returns:
            DataFrame with additional features from the group
        """
        if group_name not in self.group_functions:
            self.logger.warning(f"Unknown group: {group_name}")
            return df

        start_time = time.perf_counter()

        try:
            self.logger.info(f"Computing group: {group_name}")

            # Calculate group features
            result_df = self.group_functions[group_name](df, **kwargs)

            # Log group completion
            elapsed = time.perf_counter() - start_time
            new_features = [col for col in result_df.columns if col not in df.columns]

            self.logger.info(
                f"Group {group_name} completed: {len(new_features)} features, {elapsed:.2f}s"
            )

            return result_df

        except Exception as e:
            self.logger.error(f"Error calculating group {group_name}: {e}")
            raise FeatureError(f"Failed to calculate group {group_name}: {e}") from e

    def persist_batch(self, df: pd.DataFrame, group_name: str, **kwargs) -> bool:
        """
        Persist a batch of calculated features to database using optimized UPSERT.

        Args:
            df: DataFrame with calculated features
            group_name: Name of the group being persisted
            **kwargs: Additional parameters for persistence

        Returns:
            True if successful, False otherwise
        """
        try:
            # Use optimized UPSERT with retry logic
            success = self.upsert_optimizer.upsert_batch(
                df, group_name, table_name="indicators", **kwargs
            )

            if success:
                self.logger.info(f"Successfully persisted batch for group {group_name}")
            else:
                self.logger.error(f"Failed to persist batch for group {group_name}")

            return success

        except Exception as e:
            self.logger.error(f"Error persisting batch for group {group_name}: {e}")
            return False

    def calculate_all_groups(self, df_ohlcv: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Calculate all groups in sequence with batch persistence.

        Args:
            df_ohlcv: DataFrame with OHLCV data
            **kwargs: Additional parameters for calculation

        Returns:
            DataFrame with all calculated features
        """
        # Start metrics collection
        start_calculation_metrics(
            symbol=kwargs.get("symbol", "unknown"),
            timeframe=kwargs.get("timeframe", "unknown"),
            feature_count=len(self.config.calculation_order),
        )

        try:
            # Ensure timestamp column is present and normalized
            result_df = ensure_ts_column(df_ohlcv)

            # Validate input data
            ts_validation = strict_timestamp_validation(result_df)
            if not ts_validation["valid"]:
                raise FeatureError(
                    f"Timestamp validation failed: {ts_validation['errors']}"
                )

            self.logger.info(
                f"Starting group-based calculation for {len(result_df)} bars"
            )

            # Calculate each group in sequence
            for group_name in self.config.calculation_order:
                try:
                    # Calculate group features
                    result_df = self.calculate_group(result_df, group_name, **kwargs)

                    # Persist batch immediately
                    success = self.persist_batch(result_df, group_name, **kwargs)
                    if not success:
                        self.logger.warning(
                            f"Failed to persist batch for group {group_name}"
                        )

                    # Record metrics for the group
                    group_features = [
                        col
                        for col in result_df.columns
                        if col not in ["ts", "open", "high", "low", "close", "volume"]
                    ]

                    if group_features:
                        # Calculate fill rate for this group
                        group_df = result_df[group_features]
                        fill_rate = group_df.notna().mean().mean()
                        record_fill_rate(group_name, fill_rate)

                except Exception as e:
                    self.logger.error(f"Failed to process group {group_name}: {e}")
                    # Continue with next group instead of failing completely
                    continue

            # Final gate validation
            gate_valid, gate_result = validate_data_gate(result_df)
            if not gate_valid:
                self.logger.error(f"Gate validation failed: {gate_result['errors']}")
                raise FeatureError(f"Gate validation failed: {gate_result['errors']}")

            # Additional code validations
            feature_periods = {
                "sma_20": 20,
                "sma_50": 50,
                "sma_200": 200,
                "ema_8": 8,
                "ema_21": 21,
                "ema_50": 50,
                "atr_14": 14,
                "atr_21": 21,
            }

            code_valid, code_result = self.code_validator.validate_all(
                result_df, feature_periods
            )
            if not code_valid:
                self.logger.error(f"Code validations failed: {code_result['errors']}")
                # Don't raise error, just log warnings for additional validations
                self.logger.warning("Continuing despite code validation failures")

            # Log validation results
            if code_result["warnings"]:
                self.logger.warning(
                    f"Code validation warnings: {code_result['warnings']}"
                )

            # Calculate and record final metrics
            feature_groups = {
                "overlap": [
                    col
                    for col in result_df.columns
                    if col.startswith(("hlc3", "hl2", "ohlc4", "wcp"))
                ],
                "moving_averages": [
                    col
                    for col in result_df.columns
                    if col.startswith(("sma_", "ema_", "wma_", "hma_"))
                ],
                "oscillators": [
                    col
                    for col in result_df.columns
                    if col.startswith(("rsi_", "macd", "stoch", "cci_"))
                ],
                "volatility": [
                    col
                    for col in result_df.columns
                    if col.startswith(("atr_", "bb_", "kc_", "dc_"))
                ],
                "volume": [
                    col
                    for col in result_df.columns
                    if col.startswith(("obv", "cmf", "vwap", "mfi_"))
                ],
                "trend": [
                    col
                    for col in result_df.columns
                    if col.startswith(("adx_", "aroon", "supertrend", "psar"))
                ],
            }

            # Record fill rates by group
            fill_rates = calculate_fill_rates(result_df, feature_groups)
            for group_name, fill_rate in fill_rates.items():
                record_fill_rate(group_name, fill_rate)

            # Record quality metrics
            nan_ratio, outlier_ratio, quality_score = calculate_quality_score(result_df)
            record_quality_metrics(nan_ratio, outlier_ratio, quality_score)

            # Finish metrics collection (с защитой от ошибок при параллельном выполнении)
            final_metrics = None
            try:
                final_metrics = finish_calculation_metrics()
            except ValueError as e:
                # Ошибка метрик при параллельном выполнении - логируем, но не прерываем расчёт
                if "No active calculation to finish" in str(e):
                    self.logger.warning(
                        f"Metrics collection error (parallel execution): {e}. "
                        "Calculation completed successfully, but metrics were not recorded."
                    )
                else:
                    self.logger.warning(f"Metrics collection error: {e}")
            except Exception as e:
                # Любые другие ошибки метрик - логируем, но не прерываем расчёт
                self.logger.warning(f"Unexpected error in metrics collection: {e}")

            # Add UPSERT statistics
            upsert_stats = self.upsert_optimizer.get_statistics()
            if final_metrics is not None:
                if isinstance(upsert_stats, dict):
                    # Update metrics with UPSERT stats if they're in a dict format
                    for key, value in upsert_stats.items():
                        if hasattr(final_metrics, key):
                            setattr(final_metrics, key, value)

                self.logger.info("Group-based calculation completed successfully")
                self.logger.info(
                    f"Final metrics: rows_written={final_metrics.rows_written}, quality_score={final_metrics.data_quality_score:.2f}"
                )
            else:
                self.logger.info("Group-based calculation completed successfully (metrics not available)")

            self.logger.info(f"UPSERT stats: {upsert_stats}")

            return result_df

        except Exception as e:
            self.logger.error(f"Group-based calculation failed: {e}")
            raise FeatureError(f"Group-based calculation failed: {e}") from e


def compute_features_grouped(
    df_ohlcv: pd.DataFrame, config: GroupCalculationConfig | None = None, **kwargs
) -> pd.DataFrame:
    """
    Calculate features using group-based architecture with batch persistence.

    This is the new recommended approach that follows the plan requirements:
    - Calculate by groups in sequence
    - Persist each group immediately as a batch
    - Better error isolation and debugging

    Args:
        df_ohlcv: DataFrame with OHLCV data
        config: Configuration for group calculation
        **kwargs: Additional parameters

    Returns:
        DataFrame with all calculated features
    """
    calculator = GroupCalculator(config)
    return calculator.calculate_all_groups(df_ohlcv, **kwargs)
