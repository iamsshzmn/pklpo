"""
Core calculation functions for feature computation.

This module contains the main calculation logic for computing technical indicators
from OHLCV data with group-based architecture and online/offline parity.

Refactored in Stage 3 to use unified pipeline logic from core/pipeline.py.
Phase 2.1: Added DIP compliance with optional normalizer injection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..domain.protocols import FeatureNormalizer

from src.logging import get_features_logger, performance_timer

from ..domain.models import FeatureError
from ..indicator_groups import get_ordered_groups
from ..specs import FEATURE_SPECS, FeatureSpec
from ..utils.dependency_resolver import resolve_dependencies
from ..utils.time_utils import validate_timestamp_consistency
from .debug_utils import _debug_log_dataframe_info
from .group_orchestrator import GroupCalculationConfig, compute_features_grouped
from .merging import merge_indicator_results
from .normalization import normalize_and_finalize_result
from .pipeline import (
    PipelineContext,
    log_feature_fill_rates,
    run_post_calculation,
    run_pre_calculation,
)
from .validation import _prepare_feature_specs

logger = get_features_logger(__name__)


@performance_timer(get_features_logger("features.compute"), "compute_features")
def compute_features(
    df_ohlcv: pd.DataFrame,
    specs: list[str | FeatureSpec] | None = None,
    available: set[str] | None = None,  # For backward compatibility
    volatility_normalize: bool = True,
    normalize_window: int = 20,
    normalize_method: str = "rolling_std",
    debug: bool = False,  # New debug parameter
    critical_indicators: list[str] | None = None,
    **kwargs: dict[str, object],
) -> pd.DataFrame:
    """
    Calculate technical indicators from OHLCV data without look-ahead bias.

    Provides a unified interface for calculating technical features ensuring
    consistent results between online and offline modes. Supports volatility
    normalization and group-based calculation architecture.

    Args:
        df_ohlcv: DataFrame with OHLCV data (columns: open, high, low, close, volume)
        specs: List of feature specifications or feature names to calculate.
               If None, calculates all available features.
        available: Set of available indicator names (for backward compatibility with calc_indicators)
        volatility_normalize: Whether to apply volatility normalization
        normalize_window: Window size for volatility calculation
        normalize_method: Method for volatility normalization ("rolling_std", "ewm_std")
        debug: Enable detailed debug logging
        critical_indicators: Optional list of indicators that must be included
            even if they are not present in `specs`.
        **kwargs: Additional parameters for feature calculation (symbol, timeframe, etc.)

    Returns:
        DataFrame with calculated features. Original OHLCV columns are preserved.

    Raises:
        FeatureError: If input validation fails or calculation errors occur

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'open': [100, 101, 102],
        ...     'high': [105, 106, 107],
        ...     'low': [99, 100, 101],
        ...     'close': [104, 105, 106],
        ...     'volume': [1000, 1100, 1200]
        ... })
        >>> result = compute_features(df, specs=['rsi_14', 'sma_20'])
        >>> 'rsi_14' in result.columns
        True
    """
    if debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled via compute_features(debug=True)")

    # Create pipeline context
    symbol = str(kwargs.get("symbol", "unknown"))
    timeframe = str(kwargs.get("timeframe", "unknown"))
    ctx = PipelineContext(
        symbol=symbol,
        timeframe=timeframe,
        feature_count=len(specs) if specs else len(FEATURE_SPECS),
        debug=debug,
    )

    try:
        _debug_log_dataframe_info(df_ohlcv, "INPUT OHLCV", debug=ctx.debug)

        # Handle backward compatibility with calc_indicators interface
        if available is not None and specs is None:
            specs = list(available)

        # Convert feature names to specs if needed
        feature_specs = _prepare_feature_specs(specs)

        # Run pre-calculation phase (validation, timestamps, metrics start)
        result_df = run_pre_calculation(
            df_ohlcv, ctx, feature_specs, validate_specs=True
        )

        # Calculate features using group-based approach
        result_df = _calculate_features_internal(
            result_df,
            feature_specs,
            ctx,
            critical_indicators=critical_indicators,
            **kwargs,
        )
        _debug_log_dataframe_info(result_df, "AFTER CALCULATION", debug=ctx.debug)

        # Apply volatility normalization if requested
        if volatility_normalize:
            result_df = _apply_volatility_normalization(
                result_df, ctx, normalize_window, normalize_method
            )

        # Log feature fill rates (diagnostics)
        log_feature_fill_rates(result_df, ctx)

        # Run post-calculation phase (gate validation, metrics recording)
        result_df = run_post_calculation(result_df, ctx)

        logger.info(
            f"[{ctx.run_id}] Successfully calculated {len(feature_specs)} features for {len(df_ohlcv)} bars"
        )
        return result_df

    except Exception as e:
        import traceback

        logger.error(f"[{ctx.run_id}] Feature calculation failed: {e!s}")
        logger.error(f"[{ctx.run_id}] Traceback: {traceback.format_exc()}")
        raise FeatureError(f"Feature calculation failed: {e!s}") from e


def _apply_volatility_normalization(
    result_df: pd.DataFrame,
    ctx: PipelineContext,
    normalize_window: int,
    normalize_method: str,
    normalizer: FeatureNormalizer | None = None,
) -> pd.DataFrame:
    """Apply volatility normalization to calculated features.

    This function follows the Dependency Inversion Principle (DIP):
    It depends on the FeatureNormalizer Protocol, not concrete implementations.

    Args:
        result_df: DataFrame with calculated features
        ctx: Pipeline context
        normalize_window: Window size for volatility calculation
        normalize_method: Normalization method
        normalizer: Optional custom normalizer implementing FeatureNormalizer Protocol.
                   If None, uses the default volatility_normalize_features.

    Returns:
        DataFrame with normalized features
    """

    try:
        # Use injected normalizer if provided (DIP compliance)
        if normalizer is not None:
            logger.debug(
                f"[{ctx.run_id}] Using injected normalizer "
                f"window={normalize_window}"
            )
            return normalizer.normalize(result_df, window=normalize_window)

        # Default behavior: use built-in volatility_normalize_features
        from ..utils import volatility_normalize_features

        logger.debug(
            f"[{ctx.run_id}] Applying volatility normalization "
            f"window={normalize_window} method={normalize_method}"
        )

        if volatility_normalize_features is not None and callable(
            volatility_normalize_features
        ):
            result_df = volatility_normalize_features(
                result_df, window=normalize_window, method=normalize_method
            )
        elif volatility_normalize_features is None:
            logger.warning(
                f"[{ctx.run_id}] volatility_normalize_features is None, skipping"
            )
        else:
            logger.warning(
                f"[{ctx.run_id}] volatility_normalize_features not callable, skipping"
            )

    except Exception as e:
        logger.warning(f"[{ctx.run_id}] Failed to apply volatility normalization: {e}")

    return result_df


def _calculate_features_internal(
    result_df: pd.DataFrame,
    feature_specs: list[FeatureSpec],
    ctx: PipelineContext,
    *,
    critical_indicators: list[str] | None = None,
    **kwargs: dict[str, object],
) -> pd.DataFrame:
    """
    Calculate features based on specifications (internal implementation).

    This function performs the actual indicator calculation after pre-validation.
    It's called by compute_features() after run_pre_calculation().

    Args:
        result_df: Pre-validated OHLCV DataFrame (already has ts column, numeric dtypes)
        feature_specs: List of feature specifications
        ctx: Pipeline context with run_id, symbol, timeframe
        **kwargs: Additional parameters for feature calculation

    Returns:
        DataFrame with calculated features

    Raises:
        FeatureError: If calculation fails or data quality is insufficient
    """
    logger.debug(
        f"[{ctx.run_id}] _calculate_features_internal called "
        f"specs_count={len(feature_specs)} rows_count={len(result_df)}"
    )

    # Debug: check OHLCV data
    if ctx.debug:
        for col in ("open", "high", "low", "close", "volume"):
            if col in result_df.columns:
                non_null_count = result_df[col].notna().sum()
                logger.debug(
                    f"[{ctx.run_id}] {col} non_null={non_null_count}/{len(result_df)}"
                )

    # Validate timestamp consistency (legacy check for backward compatibility)
    if not validate_timestamp_consistency(result_df):
        logger.warning(
            f"[{ctx.run_id}] Timestamp consistency validation failed - continuing"
        )

    # Calculate features using group-based approach
    available_names = {spec.name for spec in feature_specs}

    # Add aliases for renamed indicators
    if "ichimoku_chikou" in available_names:
        available_names.add("ics_26")
    if "ics_26" in available_names and "ichimoku_chikou" not in available_names:
        available_names.add("ichimoku_chikou")
        logger.debug(f"[{ctx.run_id}] Added ichimoku_chikou for ics_26 calculation")

    # Critical indicators from explicit parameter (OCP compliance)
    if critical_indicators is None:
        critical_indicators = ["t3_20", "rma_20", "ics_26"]

    for crit_ind in critical_indicators:
        if crit_ind not in available_names:
            available_names.add(crit_ind)
            logger.debug(f"[{ctx.run_id}] Added critical indicator {crit_ind}")

    # Ensure ichimoku_chikou is added for ics_26
    if "ics_26" in available_names and "ichimoku_chikou" not in available_names:
        available_names.add("ichimoku_chikou")

    # Resolve dependencies based on registry
    available_names = resolve_dependencies(available_names)
    logger.debug(
        f"[{ctx.run_id}] After dependency resolution: {len(available_names)} indicators"
    )

    # Calculate all indicator groups
    result: dict[str, pd.Series | pd.DataFrame | object] = {}
    logger.info(f"[{ctx.run_id}] Calculating {len(available_names)} indicators")

    # Calculate indicators by groups in order defined by registry
    ordered_groups = get_ordered_groups()

    for group_name, group_calculator in ordered_groups:
        try:
            group_result = group_calculator(result_df, available_names)
            if group_result is None:
                logger.error(f"[{ctx.run_id}] {group_name} group returned None")
                ctx.failed_groups.append(group_name)
                raise FeatureError(f"{group_name} group calculator returned None")

            # Handle MACD histogram calculation if needed
            if group_name == "oscillators":
                group_result = _ensure_macd_histogram(group_result, available_names)

            result.update(group_result)
            logger.debug(
                f"[{ctx.run_id}] {group_name}: added {len(group_result)} indicators"
            )

        except FeatureError:
            raise
        except Exception as e:
            logger.error(
                f"[{ctx.run_id}] Error in {group_name} group: {e}", exc_info=True
            )
            ctx.failed_groups.append(group_name)
            raise FeatureError(f"Error calculating {group_name} group: {e}") from e

    # Merge calculated indicators into result DataFrame
    result_df = merge_indicator_results(result, result_df, available_names)

    # Normalize and finalize result DataFrame
    return normalize_and_finalize_result(result_df, debug=ctx.debug)


def _ensure_macd_histogram(
    group_result: dict[str, pd.Series | pd.DataFrame | object],
    available_names: set[str],
) -> dict[str, pd.Series | pd.DataFrame | object]:
    """Ensure MACD histogram is calculated if MACD and signal are present.

    Args:
        group_result: Results from oscillators group calculation
        available_names: Set of requested indicator names

    Returns:
        Updated group_result with macd_histogram if applicable
    """
    has_macd = "macd" in group_result
    has_macd_signal = "macd_signal" in group_result
    has_macd_histogram = "macd_histogram" in group_result

    if has_macd and has_macd_signal and not has_macd_histogram:
        macd_val = group_result["macd"]
        macd_signal_val = group_result["macd_signal"]
        if isinstance(macd_val, pd.Series) and isinstance(macd_signal_val, pd.Series):
            group_result["macd_histogram"] = macd_val - macd_signal_val
            available_names.add("macd_histogram")

    return group_result


def compute_features_new(
    df_ohlcv: pd.DataFrame,
    specs: list[str | FeatureSpec] | None = None,
    available: set[str] | None = None,
    volatility_normalize: bool = True,
    normalize_window: int = 20,
    normalize_method: str = "rolling_std",
    use_grouped_calculation: bool = True,
    **kwargs: dict[str, object],
) -> pd.DataFrame:
    """
    Unified interface for calculating features with group-based architecture.

    .. deprecated::
        Use `compute_features()` directly - it now uses unified pipeline logic.
        This function will be removed in a future version.

    Args:
        df_ohlcv: DataFrame with OHLCV data (columns: open, high, low, close, volume)
        specs: List of feature specifications or feature names to calculate.
               If None, calculates all available features.
        available: Set of available indicator names (for backward compatibility)
        volatility_normalize: Whether to apply volatility normalization
        normalize_window: Window size for volatility calculation
        normalize_method: Method for volatility normalization ("rolling_std", "ewm_std")
        use_grouped_calculation: Whether to use group-based calculation (default True)
        **kwargs: Additional parameters for feature calculation (symbol, timeframe, etc.)

    Returns:
        DataFrame with calculated features. Original OHLCV columns are preserved.

    Raises:
        FeatureError: If calculation fails or input validation errors occur
    """
    import warnings

    warnings.warn(
        "compute_features_new() is deprecated. Use compute_features() directly - "
        "it now uses unified pipeline logic.",
        DeprecationWarning,
        stacklevel=2,
    )

    if use_grouped_calculation:
        # Use group-based calculation with batch persistence
        config = GroupCalculationConfig()

        # Add calculation parameters to kwargs
        kwargs["volatility_normalize"] = volatility_normalize  # type: ignore[assignment]
        kwargs["normalize_window"] = normalize_window  # type: ignore[assignment]
        kwargs["normalize_method"] = normalize_method  # type: ignore[assignment]

        return compute_features_grouped(df_ohlcv, config=config, **kwargs)

    # Use standard calculation (now uses unified pipeline)
    return compute_features(
        df_ohlcv,
        specs,
        available,
        volatility_normalize,
        normalize_window,
        normalize_method,
        **kwargs,
    )
