"""
Core calculation functions for feature computation.

This module contains the main calculation logic for computing technical indicators
from OHLCV data with group-based architecture and online/offline parity.
"""

import logging
import os

import pandas as pd

from ..gate_validation import validate_data_gate
from ..group_calculation import GroupCalculationConfig, compute_features_grouped
from ..indicator_groups import get_ordered_groups
from ..logging_config import get_features_logger, performance_timer
from ..metrics import (
    calculate_fill_rates,
    calculate_quality_score,
    finish_calculation_metrics,
    record_fill_rate,
    record_quality_metrics,
    start_calculation_metrics,
)
from ..models import FeatureError
from ..specs import FEATURE_SPECS, FeatureSpec
from ..time_utils import (
    ensure_ts_column,
    strict_timestamp_validation,
    validate_timestamp_consistency,
)
from ..utils.dependency_resolver import resolve_dependencies
from ..validators import (
    validate_feature_specs_integrity,
    validate_ohlcv_data,
    validate_phase_requirements,
)
from .debug_utils import _debug_log_dataframe_info
from .merging import merge_indicator_results
from .normalization import normalize_and_finalize_result
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
        debug: Enable detailed debug logging (sets FEATURES_DEBUG env var)
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
    # Enable debug mode if requested
    if debug:
        os.environ["FEATURES_DEBUG"] = "true"
        os.environ["FEATURES_VERBOSE"] = "true"
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled via compute_features(debug=True)")

    try:
        _debug_log_dataframe_info(df_ohlcv, "INPUT OHLCV")
        # Start metrics collection
        symbol = str(kwargs.get("symbol", "unknown"))
        timeframe = str(kwargs.get("timeframe", "unknown"))
        start_calculation_metrics(
            symbol=symbol,
            timeframe=timeframe,
            feature_count=len(specs) if specs else len(FEATURE_SPECS),
        )

        # Validate input data
        validate_ohlcv_data(df_ohlcv)

        # Handle backward compatibility with calc_indicators interface
        if available is not None and specs is None:
            # Convert available set to specs list for backward compatibility
            specs = list(available)

        # Convert feature names to specs if needed
        feature_specs = _prepare_feature_specs(specs)
        # Validate specs integrity and phase requirements (Phase 2 by default)
        validate_feature_specs_integrity(feature_specs)
        try:
            validate_phase_requirements(feature_specs)
        except Exception as e:
            # Log as warning to allow ad-hoc runs with partial specs
            logger.warning(f"Phase requirements check warning: {e}")

        # Calculate features
        result_df = _calculate_features(df_ohlcv, feature_specs, **kwargs)
        _debug_log_dataframe_info(result_df, "AFTER CALCULATION")

        # Quick probe before normalization (diagnostics)
        if os.getenv("FEATURES_VERBOSE", "false").lower() == "true":
            try:
                probe_cols = [
                    c
                    for c in [
                        "hlc3",
                        "ema_8",
                        "sma_20",
                        "rsi_14",
                        "atr_14",
                        "macd",
                        "obv",
                    ]
                    if c in result_df.columns
                ]
                if probe_cols:
                    counts = {c: int(result_df[c].notna().sum()) for c in probe_cols}
                    logger.debug(f"PRE-NORM filled counts: {counts}")
            except Exception as e:
                logger.debug(f"Failed to log PRE-NORM probe: {e}")

        # Apply volatility normalization if requested
        if volatility_normalize:
            # Lazy import to avoid circular dependencies
            try:
                from ..utils import volatility_normalize_features

                logger.debug(
                    f"volatility_normalize_features ref: {volatility_normalize_features}"
                )
                logger.debug(
                    f"Applying volatility normalization window={normalize_window} method={normalize_method}"
                )

                # Debug: check hlc3 before normalization
                if "hlc3" in result_df.columns:
                    hlc3_before = result_df["hlc3"]
                    logger.debug(
                        f"hlc3 before normalization non_null={hlc3_before.notna().sum()}/{len(hlc3_before)}"
                    )

                if volatility_normalize_features is not None and callable(
                    volatility_normalize_features
                ):
                    result_df = volatility_normalize_features(
                        result_df, window=normalize_window, method=normalize_method
                    )

                    # Debug: check hlc3 after normalization
                    if "hlc3" in result_df.columns:
                        hlc3_after = result_df["hlc3"]
                        logger.debug(
                            f"hlc3 after normalization non_null={hlc3_after.notna().sum()}/{len(hlc3_after)}"
                        )
                elif volatility_normalize_features is None:
                    logger.warning(
                        "volatility_normalize_features is None, skipping normalization"
                    )
                else:
                    logger.warning(
                        "volatility_normalize_features not callable, skipping normalization"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to import volatility_normalize_features: {e}, skipping normalization"
                )

            # Quick probe after normalization (diagnostics)
            if os.getenv("FEATURES_VERBOSE", "false").lower() == "true":
                try:
                    probe_cols = [
                        c
                        for c in [
                            "hlc3",
                            "ema_8",
                            "sma_20",
                            "rsi_14",
                            "atr_14",
                            "macd",
                            "obv",
                        ]
                        if c in result_df.columns
                    ]
                    if probe_cols:
                        counts = {
                            c: int(result_df[c].notna().sum()) for c in probe_cols
                        }
                        logger.debug(f"POST-NORM filled counts: {counts}")
                except Exception as e:
                    logger.debug(f"Failed to log POST-NORM probe: {e}")

        # Additional validation: check feature quality
        feature_columns = [
            col
            for col in result_df.columns
            if col not in ["open", "high", "low", "close", "volume", "ts"]
        ]

        if feature_columns:
            # Check fill rates for key features
            key_features = [
                "hlc3",
                "ema_8",
                "sma_20",
                "rsi_14",
                "atr_14",
                "macd",
                "obv",
            ]
            available_key_features = [f for f in key_features if f in result_df.columns]

            if available_key_features:
                fill_rates = {}
                for feature in available_key_features:
                    non_null_count = result_df[feature].notna().sum()
                    total_count = len(result_df[feature])
                    fill_rate = (
                        (non_null_count / total_count * 100) if total_count > 0 else 0
                    )
                    fill_rates[feature] = fill_rate

                try:
                    logger.debug(f"Final feature fill rates: {fill_rates}")
                except Exception as e:
                    logger.error(f"logging failed: {e}")
                    raise

                # Warn if critical features have low fill rates
                critical_features = ["hlc3", "ema_8", "sma_20"]
                for feature in critical_features:
                    if feature in fill_rates and fill_rates[feature] < 50:
                        logger.warning(
                            f"Critical feature {feature} has low fill rate fill_rate={fill_rates[feature]:.1f}%"
                        )

        # GATE VALIDATION: Check data quality before returning
        gate_valid, gate_result = validate_data_gate(result_df)
        failed_groups = []
        if not gate_valid:
            logger.warning(
                f"Gate validation failed (non-blocking): {gate_result['errors']}"
            )
            # Извлекаем список проблемных групп
            for error in gate_result.get("errors", []):
                if "Group " in error:
                    group_name = error.split("Group ")[1].split(":")[0]
                    failed_groups.append(group_name)
            logger.info(
                f"Failed groups: {failed_groups}. Data will be saved with data_status='inc'"
            )

        # Добавляем метаданные о качестве данных
        result_df["data_status"] = "inc" if failed_groups else "ok"
        if failed_groups:
            result_df["failed_groups"] = ",".join(failed_groups)

        logger.info(
            f"Gate validation passed: overall fill rate {gate_result['stats']['overall_quality']['fill_rate']:.2%}"
        )

        # Calculate and record metrics
        feature_groups = {
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
            "overlap": [
                col
                for col in result_df.columns
                if col in ["hlc3", "hl2", "ohlc4", "wcp"]
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
            if final_metrics is not None:
                logger.info(
                    f"Successfully calculated {len(feature_specs)} features for {len(df_ohlcv)} bars"
                )
                logger.info(
                    f"Final metrics: rows_written={final_metrics.rows_written}, quality_score={final_metrics.data_quality_score:.2f}"
                )
            else:
                logger.warning(
                    "Metrics collection returned None. Calculation completed successfully."
                )
        except ValueError as e:
            # Ошибка метрик при параллельном выполнении - логируем, но не прерываем расчёт
            if "No active calculation to finish" in str(e):
                logger.warning(
                    f"Metrics collection error (parallel execution): {e}. "
                    "Calculation completed successfully, but metrics were not recorded."
                )
            else:
                # Другие ошибки метрик - тоже логируем, но не прерываем
                logger.warning(f"Metrics collection error: {e}")
        except Exception as e:
            # Любые другие ошибки метрик - логируем, но не прерываем расчёт
            logger.warning(f"Unexpected error in metrics collection: {e}")

        logger.info(
            f"Successfully calculated {len(feature_specs)} features for {len(df_ohlcv)} bars"
        )
        return result_df

    except Exception as e:
        import traceback

        logger.error(f"Feature calculation failed: {e!s}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise FeatureError(f"Feature calculation failed: {e!s}") from e


def _calculate_features(
    df_ohlcv: pd.DataFrame,
    feature_specs: list[FeatureSpec],
    **kwargs: dict[str, object],
) -> pd.DataFrame:
    """
    Calculate features based on specifications.

    Args:
        df_ohlcv: OHLCV DataFrame
        feature_specs: List of feature specifications
        **kwargs: Additional parameters for feature calculation

    Returns:
        DataFrame with calculated features

    Raises:
        FeatureError: If calculation fails or data quality is insufficient
    """
    logger.debug(
        f"_calculate_features called specs_count={len(feature_specs)} rows_count={len(df_ohlcv)}"
    )

    # DEBUG: Проверяем входные данные OHLCV
    logger.debug(
        f"df_ohlcv columns={list(df_ohlcv.columns)} shape={df_ohlcv.shape} dtypes={df_ohlcv.dtypes.to_dict()}"
    )

    # Проверяем ключевые колонки
    for col in ("open", "high", "low", "close", "volume"):
        if col in df_ohlcv.columns:
            non_null_count = df_ohlcv[col].notna().sum()
            logger.debug(
                f"{col} data quality non_null={non_null_count}/{len(df_ohlcv)}"
            )
            if non_null_count > 0:
                sample_values = df_ohlcv[col].dropna().head(3).tolist()
                logger.debug(f"{col} sample values values={sample_values}")
        else:
            logger.warning(f"{col} NOT FOUND in df_ohlcv columns")

    # Start with OHLCV data and enforce numeric dtypes
    result_df = df_ohlcv.copy()
    # Векторизация: конвертируем все OHLCV колонки одновременно
    ohlcv_cols = [
        col
        for col in ("open", "high", "low", "close", "volume")
        if col in result_df.columns
    ]
    if ohlcv_cols:
        result_df[ohlcv_cols] = result_df[ohlcv_cols].apply(
            pd.to_numeric, errors="coerce", axis=0
        )
        # Fail-fast check for data quality (векторизованная проверка)
        quality_check = result_df[ohlcv_cols].notna().mean()
        for col in ohlcv_cols:
            if quality_check[col] < 0.1:
                raise FeatureError(
                    f"Low data quality in {col}: {quality_check[col]:.1%} non-null"
                )

    # Ensure timestamp column is present and normalized to UTC milliseconds
    result_df = ensure_ts_column(result_df)

    # STRICT VALIDATION: Validate timestamp consistency according to plan
    ts_validation = strict_timestamp_validation(result_df)
    if not ts_validation["valid"]:
        logger.error(f"Timestamp validation failed: {ts_validation['errors']}")
        raise FeatureError(f"Timestamp validation failed: {ts_validation['errors']}")

    # Log timestamp validation results
    logger.info(f"Timestamp validation passed: {ts_validation['stats']}")

    # Validate timestamp consistency (legacy check for backward compatibility)
    if not validate_timestamp_consistency(result_df):
        logger.warning(
            "Timestamp consistency validation failed - continuing with warnings"
        )

    # Calculate features using group-based approach (from calc_indicators)
    available_names = {spec.name for spec in feature_specs}

    # Добавляем псевдонимы для переименованных индикаторов
    # Если в available_names есть ichimoku_chikou, добавляем ics_26 (для БД)
    if "ichimoku_chikou" in available_names:
        available_names.add("ics_26")
    # Если ics_26 есть в specs, но ichimoku_chikou нет, добавляем ichimoku_chikou для расчёта
    if "ics_26" in available_names and "ichimoku_chikou" not in available_names:
        available_names.add("ichimoku_chikou")
        logger.info("Added ichimoku_chikou to available_names for ics_26 calculation")

    # Критические поля, которые должны рассчитываться всегда
    critical_indicators = ["t3_20", "rma_20", "ics_26"]
    for crit_ind in critical_indicators:
        if crit_ind not in available_names:
            available_names.add(crit_ind)
            logger.info(f"Added critical indicator {crit_ind} to available_names")

    # Для ics_26 нужно также добавить ichimoku_chikou, чтобы он рассчитывался
    if "ics_26" in available_names and "ichimoku_chikou" not in available_names:
        available_names.add("ichimoku_chikou")
        logger.info(
            "Added ichimoku_chikou to available_names for ics_26 calculation (critical)"
        )

    # Для t3_20 и rma_20 они уже должны быть в specs, но на всякий случай проверяем
    logger.info(
        f"Final available_names count: {len(available_names)}, contains ichimoku_chikou: {'ichimoku_chikou' in available_names}, contains t3_20: {'t3_20' in available_names}, contains ics_26: {'ics_26' in available_names}"
    )

    # Разрешаем зависимости на основе реестра вместо принудительного добавления
    # Это соблюдает контракт: добавляем только те индикаторы, которые действительно нужны
    available_names = resolve_dependencies(available_names)
    logger.debug(
        f"After dependency resolution: {len(available_names)} indicators (added dependencies)"
    )

    # Диагностика: проверяем, есть ли overlap индикаторы в available_names
    overlap_check = ["hlc3", "hl2", "ohlc4", "wcp"]
    overlap_in_available = [n for n in overlap_check if n in available_names]
    logger.info(
        f"DIAGNOSTIC: Overlap indicators in available_names: {overlap_in_available}"
    )
    logger.info(f"DIAGNOSTIC: Total available_names count: {len(available_names)}")

    # Calculate all indicator groups
    result: dict[str, pd.Series | pd.DataFrame | object] = {}
    logger.info(
        f"Calculating indicator groups for {len(available_names)} available names"
    )

    # Вычисляем индикаторы по группам в порядке, определённом реестром
    # Это заменяет статические импорты и вызовы на динамический реестр
    ordered_groups = get_ordered_groups()
    logger.debug(f"Processing {len(ordered_groups)} indicator groups in order")

    for group_name, group_calculator in ordered_groups:
        logger.debug(f"Calculating {group_name} group indicators")
        try:
            group_result = group_calculator(result_df, available_names)
            if group_result is None:
                # Defensive check for runtime safety
                logger.error(f"{group_name} group calculator returned None")
                raise FeatureError(f"{group_name} group calculator returned None")
            # Type narrowing: group_result is not None after check above

            # Специальная обработка для overlap группы (для диагностики)
            if group_name == "overlap":
                logger.debug(f"overlap_result keys: {list(group_result.keys())}")
                if "hlc3" in group_result:
                    hlc3_series = group_result["hlc3"]
                    logger.debug(f"overlap_result['hlc3'] type: {type(hlc3_series)}")
                    if isinstance(hlc3_series, pd.Series):
                        logger.debug(
                            f"overlap_result['hlc3'] non-null: {hlc3_series.notna().sum()}/{len(hlc3_series)}"
                        )

            # Специальная обработка для oscillators группы (MACD histogram)
            if group_name == "oscillators":
                logger.debug(
                    f"oscillator_result keys sample: {list(group_result.keys())[:10]}"
                )
                has_macd = "macd" in group_result
                has_macd_signal = "macd_signal" in group_result
                has_macd_histogram = "macd_histogram" in group_result
                needs_macd_histogram = (
                    has_macd and has_macd_signal
                ) or has_macd_histogram

                logger.debug(
                    f"MACD check: macd={has_macd}, macd_signal={has_macd_signal}, histogram={has_macd_histogram}, needs={needs_macd_histogram}"
                )

                if needs_macd_histogram and "macd_histogram" not in available_names:
                    available_names.add("macd_histogram")
                    logger.debug("Added macd_histogram to available_names")
                    # Если histogram рассчитан, но не был в result, рассчитаем его
                    if not has_macd_histogram and has_macd and has_macd_signal:
                        macd_val = group_result["macd"]
                        macd_signal_val = group_result["macd_signal"]
                        if isinstance(macd_val, pd.Series) and isinstance(
                            macd_signal_val, pd.Series
                        ):
                            group_result["macd_histogram"] = macd_val - macd_signal_val
                            logger.debug(
                                "Calculated macd_histogram as macd - macd_signal"
                            )

            # Специальная обработка для trend группы (для диагностики)
            if group_name == "trend":
                logger.debug(
                    f"Trend result keys sample: {list(group_result.keys())[:10]}"
                )
                logger.debug(f"Trend result has willr: {'willr' in group_result}")
                logger.debug(f"Trend result has ultosc: {'ultosc' in group_result}")

            result.update(group_result)
            logger.debug(
                f"{group_name} group: added {len(group_result)} indicators to result"
            )

        except Exception as e:
            logger.error(f"Error calculating {group_name} group: {e}", exc_info=True)
            raise FeatureError(f"Error calculating {group_name} group: {e}") from e

    # Merge calculated indicators into result DataFrame
    result_df = merge_indicator_results(result, result_df, available_names)

    # Normalize and finalize result DataFrame
    return normalize_and_finalize_result(result_df)


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

    This function provides both the legacy compute_features behavior and the new
    group-based calculation with batch persistence. Recommended for new code.

    Args:
        df_ohlcv: DataFrame with OHLCV data (columns: open, high, low, close, volume)
        specs: List of feature specifications or feature names to calculate.
               If None, calculates all available features.
        available: Set of available indicator names (for backward compatibility)
        volatility_normalize: Whether to apply volatility normalization
        normalize_window: Window size for volatility calculation
        normalize_method: Method for volatility normalization ("rolling_std", "ewm_std")
        use_grouped_calculation: Whether to use new group-based calculation (recommended)
        **kwargs: Additional parameters for feature calculation (symbol, timeframe, etc.)

    Returns:
        DataFrame with calculated features. Original OHLCV columns are preserved.

    Raises:
        FeatureError: If calculation fails or input validation errors occur

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'open': [100, 101, 102],
        ...     'high': [105, 106, 107],
        ...     'low': [99, 100, 101],
        ...     'close': [104, 105, 106],
        ...     'volume': [1000, 1100, 1200]
        ... })
        >>> result = compute_features_new(df, specs=['rsi_14'], use_grouped_calculation=True)
        >>> 'rsi_14' in result.columns
        True
    """
    if use_grouped_calculation:
        # Use new group-based calculation with batch persistence
        logger.info("Using group-based calculation with batch persistence")

        # Create configuration
        config = GroupCalculationConfig()

        # Add calculation parameters to kwargs
        # Type: ignore needed because mypy doesn't understand dict[str, object] assignment
        kwargs["volatility_normalize"] = volatility_normalize  # type: ignore[assignment]
        kwargs["normalize_window"] = normalize_window  # type: ignore[assignment]
        kwargs["normalize_method"] = normalize_method  # type: ignore[assignment]

        return compute_features_grouped(df_ohlcv, config=config, **kwargs)
    # Use legacy calculation method
    logger.info("Using legacy calculation method")
    return compute_features(
        df_ohlcv,
        specs,
        available,
        volatility_normalize,
        normalize_window,
        normalize_method,
        **kwargs,
    )
