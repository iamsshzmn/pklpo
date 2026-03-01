"""
Normalization and finalization logic for feature calculation results.

This module handles type normalization, column renaming, and final validation
of calculated feature DataFrames.
"""

import os

import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)


def normalize_and_finalize_result(result_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize types and finalize result DataFrame.

    Args:
        result_df: DataFrame with calculated features

    Returns:
        Normalized and finalized DataFrame
    """
    # Финальное приведение типов к float64 для всех числовых колонок (кроме служебных)
    result_df = _normalize_numeric_types(result_df)

    # Унификация имён колонок (единый словарь маппинга)
    result_df = _normalize_column_names(result_df)

    # Debug: check final state of result_df
    _debug_final_state(result_df)

    # Group-level quick debug of representative features
    _log_feature_probes(result_df)

    # Итоговая сводка по заполненности (только при verbose)
    _log_feature_summary(result_df)

    return result_df


def _normalize_numeric_types(result_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize numeric column types to float64.

    Args:
        result_df: DataFrame to normalize

    Returns:
        DataFrame with normalized types
    """
    service_cols = {
        "symbol",
        "timeframe",
        "timestamp",
        "ts",
        "data_status",
        "failed_groups",
    }
    numeric_cols = [
        c
        for c in result_df.columns
        if c not in service_cols and result_df[c].dtype in ["object", "int64", "int32"]
    ]
    if numeric_cols:
        logger.info(
            f"Converting {len(numeric_cols)} columns to float64 to avoid FutureWarning"
        )
        # Векторизация: конвертируем все колонки одновременно
        result_df[numeric_cols] = (
            result_df[numeric_cols]
            .apply(pd.to_numeric, errors="coerce", axis=0)
            .astype("float64")
        )
    return result_df


def _normalize_column_names(result_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names using rename mapping.

    Args:
        result_df: DataFrame to normalize

    Returns:
        DataFrame with normalized column names
    """
    # Унификация имён колонок (единый словарь маппинга)
    column_rename_map = {
        # Bollinger Bands
        "bbands_upper": "bb_upper",
        "bbands_middle": "bb_middle",
        "bbands_lower": "bb_lower",
        "bbands_width": "bb_width",
        "bbands_percent": "bb_percent",
        # Overlap - маппинг алиасов на канонические имена
        "midpoint": "hl2",
        "midprice": "hl2",
        # Ichimoku - маппинг для БД (ichimoku_chikou используется как ics_26 в БД)
        "ichimoku_chikou": "ics_26",
        # Vortex (уже обрабатывается в fallback, но на всякий случай)
        "vtxp": "vortex_pos",
        "vtxm": "vortex_neg",
    }

    # Применяем переименование только для существующих колонок
    # Для overlap: если hl2 уже есть, удаляем midpoint/midprice вместо переименования
    rename_dict = {}
    cols_to_drop = []
    for old, new in column_rename_map.items():
        if old in result_df.columns:
            if new in result_df.columns:
                # Целевая колонка уже существует - удаляем алиас
                cols_to_drop.append(old)
                logger.info(
                    f"Dropping duplicate alias {old} (target {new} already exists)"
                )
            else:
                # Целевой колонки нет - переименовываем
                rename_dict[old] = new

    if cols_to_drop:
        result_df = result_df.drop(columns=cols_to_drop)
        logger.info(
            f"Dropped {len(cols_to_drop)} duplicate alias columns: {cols_to_drop}"
        )

    if rename_dict:
        logger.info(
            f"Renaming {len(rename_dict)} columns for DB compatibility: {rename_dict}"
        )
        result_df = result_df.rename(columns=rename_dict)
        # Проверяем, что переименование сработало
        if "ichimoku_chikou" in rename_dict and "ics_26" in result_df.columns:
            logger.info("✅ ichimoku_chikou → ics_26 mapping applied successfully")

    return result_df


def _debug_final_state(result_df: pd.DataFrame) -> None:
    """
    Debug log final state of result DataFrame.

    Args:
        result_df: DataFrame to debug
    """
    # Debug: check final state of result_df
    if "hlc3" in result_df.columns:
        hlc3_final = result_df["hlc3"]
        logger.debug(
            f"result_df['hlc3'] final quality non_null={hlc3_final.notna().sum()}/{len(hlc3_final)}"
        )
        logger.debug(
            f"result_df['hlc3'] final sample head={hlc3_final.head(2).tolist()}"
        )
    else:
        logger.debug(f"hlc3 NOT in result_df.columns columns={list(result_df.columns)}")


def _log_feature_probes(result_df: pd.DataFrame) -> None:
    """
    Log feature probes for debugging.

    Args:
        result_df: DataFrame to probe
    """
    # Group-level quick debug of representative features
    if os.getenv("FEATURES_VERBOSE", "false").lower() == "true":
        try:
            probes = [
                c
                for c in [
                    "hlc3",
                    "ema_8",
                    "sma_20",
                    "rsi_14",
                    "atr_14",
                    "obv",
                    "macd",
                ]
                if c in result_df.columns
            ]
            if probes:
                counts = {c: int(result_df[c].notna().sum()) for c in probes}
                logger.debug(f"FEATURE PROBES filled counts: {counts}")
        except Exception as e:
            logger.debug(f"Failed to log feature probes: {e}")


def _log_feature_summary(result_df: pd.DataFrame) -> None:
    """
    Log feature summary statistics.

    Args:
        result_df: DataFrame to summarize
    """
    # Итоговая сводка по заполненности (только при verbose)
    if os.getenv("FEATURES_VERBOSE", "false").lower() == "true":
        try:
            # Get feature columns (exclude OHLCV and timestamp columns)
            exclude_cols = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "ts",
                "timestamp",
            ]
            feature_cols = [col for col in result_df.columns if col not in exclude_cols]

            if feature_cols:
                non_null_percents = (
                    result_df[feature_cols].notna().mean().sort_values(ascending=True)
                )
            else:
                non_null_percents = pd.Series(dtype=float)
            worst = non_null_percents.head(10)
            best = non_null_percents.tail(10)
            logger.debug(
                "FEATURE SUMMARY (worst 10): "
                + ", ".join([f"{k}:{v*100:.0f}%" for k, v in worst.items()])
            )
            logger.debug(
                "FEATURE SUMMARY (best 10):  "
                + ", ".join([f"{k}:{v*100:.0f}%" for k, v in best.items()])
            )
        except Exception as e:
            logger.debug(f"Failed to log feature summary: {e}")
