"""
Unified pipeline logic for feature calculation.

This module extracts common code from compute_features() and GroupCalculator
to eliminate duplication and ensure consistent behavior.

Stage 3 of refactoring plan: Унификация compute_features.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..domain.models import FeatureError
from ..observability.logging import get_features_logger
from ..observability.metrics import (
    calculate_fill_rates,
    calculate_quality_score,
    finish_calculation_metrics,
    record_fill_rate,
    record_quality_metrics,
    start_calculation_metrics,
)
from ..utils.time_utils import ensure_ts_column, strict_timestamp_validation
from ..validation.feature_validator import (
    validate_feature_specs_integrity,
    validate_ohlcv_data,
    validate_phase_requirements,
)
from ..validation.gate_validator import validate_data_gate

if TYPE_CHECKING:
    from ..specs import FeatureSpec

logger = get_features_logger(__name__)


# Standard feature groups for fill rate calculation
# Used consistently across compute_features() and GroupCalculator
FEATURE_GROUPS_PATTERNS = {
    "overlap": ["hlc3", "hl2", "ohlc4", "wcp"],
    "moving_averages": ("sma_", "ema_", "wma_", "hma_", "t3_", "rma_"),
    "oscillators": ("rsi_", "macd", "stoch", "cci_", "willr", "ultosc"),
    "volatility": ("atr_", "bb_", "kc_", "dc_", "natr_"),
    "volume": ("obv", "cmf", "vwap", "mfi_", "ad", "adosc"),
    "trend": ("adx_", "aroon", "supertrend", "psar", "ics_"),
}


@dataclass
class BaseContext:
    """Base context for feature calculation pipeline (ISP-compliant).

    Contains only common fields used by all pipeline phases.
    Task 11: Separated from group-specific fields.
    """

    symbol: str = "unknown"
    timeframe: str = "unknown"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    feature_count: int = 0


@dataclass
class GroupCalculationContext(BaseContext):
    """Extended context for group-based calculation.

    Adds fields specific to group calculation and error tracking.
    Task 11: ISP - Interface Segregation Principle.
    """

    failed_groups: list[str] = field(default_factory=list)
    data_status: str = "ok"  # 'ok', 'inc' (incomplete), or 'warmup'


# Backward compatibility alias
PipelineContext = GroupCalculationContext


def build_feature_groups(df: pd.DataFrame) -> dict[str, list[str]]:
    """Build feature groups dictionary from DataFrame columns.

    Args:
        df: DataFrame with calculated features

    Returns:
        Dictionary mapping group names to lists of column names
    """
    groups: dict[str, list[str]] = {}

    for group_name, patterns in FEATURE_GROUPS_PATTERNS.items():
        if isinstance(patterns, list):
            # Exact match for overlap columns
            groups[group_name] = [col for col in df.columns if col in patterns]
        else:
            # Prefix match for other groups
            groups[group_name] = [col for col in df.columns if col.startswith(patterns)]

    return groups


def run_pre_calculation(
    df_ohlcv: pd.DataFrame,
    ctx: PipelineContext,
    feature_specs: list[FeatureSpec] | None = None,
    validate_specs: bool = True,
) -> pd.DataFrame:
    """Run pre-calculation phase: validation, timestamps, metrics start.

    Args:
        df_ohlcv: Input OHLCV DataFrame
        ctx: Pipeline context
        feature_specs: Optional list of feature specs for validation
        validate_specs: Whether to validate feature specs

    Returns:
        Validated DataFrame with normalized timestamps

    Raises:
        FeatureError: If validation fails
    """
    logger.debug(
        f"[{ctx.run_id}] Pre-calculation started for {ctx.symbol}/{ctx.timeframe}"
    )

    # Start metrics collection
    start_calculation_metrics(
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        feature_count=ctx.feature_count,
    )

    # Validate input data
    validate_ohlcv_data(df_ohlcv)

    # Validate specs integrity and phase requirements
    if validate_specs and feature_specs:
        validate_feature_specs_integrity(feature_specs)
        try:
            validate_phase_requirements(feature_specs)
        except Exception as e:
            # Log as warning to allow ad-hoc runs with partial specs
            logger.warning(f"[{ctx.run_id}] Phase requirements check warning: {e}")

    # Create result DataFrame with normalized timestamps
    result_df = df_ohlcv.copy()

    # Ensure timestamp column is present and normalized to UTC milliseconds
    result_df = ensure_ts_column(result_df)

    # Strict timestamp validation
    ts_validation = strict_timestamp_validation(result_df)
    if not ts_validation["valid"]:
        logger.error(
            f"[{ctx.run_id}] Timestamp validation failed: {ts_validation['errors']}"
        )
        raise FeatureError(f"Timestamp validation failed: {ts_validation['errors']}")

    logger.info(f"[{ctx.run_id}] Timestamp validation passed: {ts_validation['stats']}")

    # Enforce numeric dtypes for OHLCV columns
    ohlcv_cols = [
        col
        for col in ("open", "high", "low", "close", "volume")
        if col in result_df.columns
    ]
    if ohlcv_cols:
        numeric_ohlcv = result_df[ohlcv_cols].apply(pd.to_numeric, errors="coerce", axis=0)
        # Force numpy float64 + np.nan (not nullable Float64/pd.NA) to keep pandas_ta stable.
        numeric_ohlcv = numeric_ohlcv.replace([np.inf, -np.inf], np.nan).astype("float64")
        result_df[ohlcv_cols] = numeric_ohlcv
        # Fail-fast check for data quality
        quality_check = result_df[ohlcv_cols].notna().mean()
        for col in ohlcv_cols:
            if quality_check[col] < 0.1:
                raise FeatureError(
                    f"Low data quality in {col}: {quality_check[col]:.1%} non-null"
                )

    logger.debug(f"[{ctx.run_id}] Pre-calculation completed")
    return result_df


def run_post_calculation(
    result_df: pd.DataFrame,
    ctx: PipelineContext,
) -> pd.DataFrame:
    """Run post-calculation phase: gate validation, metrics recording.

    Args:
        result_df: DataFrame with calculated features
        ctx: Pipeline context

    Returns:
        DataFrame with added metadata columns (data_status, failed_groups)
    """
    logger.debug(f"[{ctx.run_id}] Post-calculation started")

    # Gate validation
    gate_valid, gate_result = validate_data_gate(result_df)

    if not gate_valid:
        logger.warning(
            f"[{ctx.run_id}] Gate validation failed (non-blocking): {gate_result['errors']}"
        )
        # Extract failed groups from errors
        for error in gate_result.get("errors", []):
            if "Group " in error:
                group_name = error.split("Group ")[1].split(":")[0]
                if group_name not in ctx.failed_groups:
                    ctx.failed_groups.append(group_name)

        ctx.data_status = "inc"
        logger.info(
            f"[{ctx.run_id}] Failed groups: {ctx.failed_groups}. Data will be saved with data_status='inc'"
        )
    else:
        logger.info(
            f"[{ctx.run_id}] Gate validation passed: overall fill rate "
            f"{gate_result['stats']['overall_quality']['fill_rate']:.2%}"
        )

    # Add metadata columns
    result_df = result_df.copy()
    result_df["data_status"] = ctx.data_status
    if ctx.failed_groups:
        result_df["failed_groups"] = ",".join(ctx.failed_groups)

    # Calculate and record fill rates by group
    feature_groups = build_feature_groups(result_df)
    fill_rates = calculate_fill_rates(result_df, feature_groups)
    for group_name, fill_rate in fill_rates.items():
        record_fill_rate(group_name, fill_rate)

    # Record quality metrics
    nan_ratio, outlier_ratio, quality_score = calculate_quality_score(result_df)
    record_quality_metrics(nan_ratio, outlier_ratio, quality_score)

    # Finish metrics collection with error handling for parallel execution
    try:
        final_metrics = finish_calculation_metrics()
        if final_metrics is not None:
            logger.info(
                f"[{ctx.run_id}] Final metrics: rows_written={final_metrics.rows_written}, "
                f"quality_score={final_metrics.data_quality_score:.2f}"
            )
        else:
            logger.warning(f"[{ctx.run_id}] Metrics collection returned None")
    except ValueError as e:
        if "No active calculation to finish" in str(e):
            logger.warning(
                f"[{ctx.run_id}] Metrics collection error (parallel execution): {e}"
            )
        else:
            logger.warning(f"[{ctx.run_id}] Metrics collection error: {e}")
    except Exception as e:
        logger.warning(f"[{ctx.run_id}] Unexpected error in metrics collection: {e}")

    logger.debug(f"[{ctx.run_id}] Post-calculation completed")
    return result_df


def log_feature_fill_rates(
    result_df: pd.DataFrame,
    ctx: PipelineContext,
    key_features: list[str] | None = None,
) -> dict[str, float]:
    """Log fill rates for key features and return them.

    Args:
        result_df: DataFrame with calculated features
        ctx: Pipeline context
        key_features: List of key feature names to check (defaults to common indicators)

    Returns:
        Dictionary mapping feature names to fill rates (0-100%)
    """
    if key_features is None:
        key_features = ["hlc3", "ema_8", "sma_20", "rsi_14", "atr_14", "macd", "obv"]

    available_features = [f for f in key_features if f in result_df.columns]
    fill_rates: dict[str, float] = {}

    for feature in available_features:
        non_null_count = result_df[feature].notna().sum()
        total_count = len(result_df[feature])
        fill_rate = (non_null_count / total_count * 100) if total_count > 0 else 0
        fill_rates[feature] = fill_rate

    logger.debug(f"[{ctx.run_id}] Feature fill rates: {fill_rates}")

    # Warn for critical features with low fill rates
    critical_features = ["hlc3", "ema_8", "sma_20"]
    for feature in critical_features:
        if feature in fill_rates and fill_rates[feature] < 50:
            logger.warning(
                f"[{ctx.run_id}] Critical feature {feature} has low fill rate: {fill_rates[feature]:.1f}%"
            )

    return fill_rates
