"""
Group-based calculation with batch persistence.

This module implements the group-based calculation architecture as specified in the plan:
overlap → MA → oscillators → volatility → volume → trend → candles → squeeze → statistics → performance

Each group is calculated on a common DataFrame and immediately persisted as a batch.

Refactored in Stage 3 to use unified pipeline logic from core/pipeline.py.
Refactored (Task 9): Uses GroupRegistry for OCP-compliant group management.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ..domain.models import FeatureError
from ..indicator_groups.registry import GroupRegistry
from ..infrastructure.upsert_optimizer import UpsertConfig, UpsertOptimizer
from ..observability.logging import (
    LogAggregator,
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)
from ..observability.metrics import record_fill_rate
from ..validation.code_validator import CodeValidator, ValidationConfig
from .pipeline import (
    PipelineContext,
    run_post_calculation,
    run_pre_calculation,
)

if TYPE_CHECKING:
    import pandas as pd

# Public API
__all__ = [
    "CALCULATION_ORDER",
    "GroupCalculationConfig",
    "GroupCalculator",
    "compute_features_grouped",
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

logger = get_category_logger(LogCategory.CALC)


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
    """Calculator for group-based feature calculation with batch persistence.

    Refactored (Task 9): Uses GroupRegistry instead of hard-coded imports.
    This enables OCP compliance - adding new groups requires only
    registering them via @GroupRegistry.register decorator.
    """

    def __init__(self, config: GroupCalculationConfig | None = None):
        self.config = config or GroupCalculationConfig()
        self.logger = get_category_logger(LogCategory.CALC)

        # Initialize UPSERT optimizer
        self.upsert_optimizer = UpsertOptimizer(UpsertConfig())

        # Initialize code validator
        self.code_validator = CodeValidator(ValidationConfig())

        # Initialize group registry (loads groups from legacy GROUP_CALCULATORS if needed)
        self._init_registry()

    def _init_registry(self) -> None:
        """Initialize GroupRegistry and log available groups."""
        # GroupRegistry auto-loads legacy groups via _ensure_initialized()
        ordered_groups = GroupRegistry.get_ordered()
        if should_log(LogCategory.DIAG, Verbosity.DEBUG):
            group_names = [g.name for g in ordered_groups]
            self.logger.debug(
                f"GroupRegistry: {len(ordered_groups)} groups: {group_names}"
            )

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
        # Get calculator from GroupRegistry (OCP-compliant)
        calculator_fn = GroupRegistry.get_calculator(group_name)
        if calculator_fn is None:
            self.logger.warning(f"Unknown group: {group_name}")
            return df

        start_time = time.perf_counter()

        try:
            # Calculate group features via registry-provided calculator
            result_df = calculator_fn(df, **kwargs)

            # Log group completion only at DEBUG level
            if should_log(LogCategory.DIAG, Verbosity.DEBUG):
                elapsed = time.perf_counter() - start_time
                new_features = [
                    col for col in result_df.columns if col not in df.columns
                ]
                self.logger.debug(
                    f"{group_name}: {len(new_features)} features in {elapsed:.2f}s"
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

            if not success:
                self.logger.error(f"Failed to persist batch for group {group_name}")

            return success

        except Exception as e:
            self.logger.error(f"Error persisting batch for group {group_name}: {e}")
            return False

    def calculate_all_groups(self, df_ohlcv: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Calculate all groups in sequence with batch persistence.

        Uses unified pipeline from core/pipeline.py for consistent behavior
        with compute_features().

        Refactored (Task 9): Uses GroupRegistry.get_ordered() for execution order.

        Args:
            df_ohlcv: DataFrame with OHLCV data
            **kwargs: Additional parameters for calculation

        Returns:
            DataFrame with all calculated features
        """
        # Get ordered groups from registry (OCP-compliant)
        ordered_groups = GroupRegistry.get_ordered()

        # Create pipeline context
        ctx = PipelineContext(
            symbol=str(kwargs.get("symbol", "unknown")),
            timeframe=str(kwargs.get("timeframe", "unknown")),
            feature_count=len(ordered_groups),
        )

        # Use aggregator for group-level summary
        with LogAggregator(LogCategory.CALC, "group_calculation") as agg:
            try:
                # Run pre-calculation phase (validation, timestamps, metrics start)
                result_df = run_pre_calculation(df_ohlcv, ctx, validate_specs=False)

                # Calculate each group in sequence (order from registry)
                for group_entry in ordered_groups:
                    group_name = group_entry.name
                    try:
                        # Calculate group features via registry calculator
                        result_df = self.calculate_group(
                            result_df, group_name, **kwargs
                        )

                        # Persist batch immediately
                        success = self.persist_batch(result_df, group_name, **kwargs)
                        if not success:
                            agg.add_warning(f"Failed to persist {group_name}")

                        # Record fill rate for this group
                        group_features = [
                            col
                            for col in result_df.columns
                            if col
                            not in ["ts", "open", "high", "low", "close", "volume"]
                        ]
                        if group_features:
                            group_df = result_df[group_features]
                            fill_rate = group_df.notna().mean().mean()
                            record_fill_rate(group_name, fill_rate)
                            agg.add("groups", group_name, value=fill_rate)

                    except Exception as e:
                        # Record failed group and continue, but mark data as incomplete
                        agg.add_error(f"Failed to process {group_name}: {e}")
                        ctx.failed_groups.append(group_name)
                        ctx.data_status = "inc"
                        # Continue with next group - partial data is better than no data

                # Additional code validations (non-blocking)
                self._run_code_validations(result_df, ctx)

                # Run post-calculation phase (gate validation, metrics recording)
                result_df = run_post_calculation(result_df, ctx)

                # Set summary info
                agg.set_extra("bars", len(result_df))
                agg.set_extra("status", ctx.data_status)
                if ctx.failed_groups:
                    agg.set_extra("failed", len(ctx.failed_groups))

                return result_df

            except Exception as e:
                self.logger.error(f"Group-based calculation failed: {e}")
                raise FeatureError(f"Group-based calculation failed: {e}") from e

    def _run_code_validations(
        self, result_df: pd.DataFrame, ctx: PipelineContext
    ) -> None:
        """Run additional code validations (non-blocking).

        Args:
            result_df: DataFrame with calculated features
            ctx: Pipeline context
        """
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

        if not code_valid and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
            self.logger.warning(f"Code validations failed: {code_result['errors']}")

        if code_result.get("warnings") and should_log(
            LogCategory.DIAG, Verbosity.VERBOSE
        ):
            self.logger.warning(f"Code validation warnings: {code_result['warnings']}")


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
