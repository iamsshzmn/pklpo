"""
Диагностические функции для работы с DataFrame и схемой данных.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def check_df_schema(df: pd.DataFrame, expected_cols: set[str]) -> dict[str, Any]:
    """
    Проверяет соответствие схемы DataFrame и ожидаемых колонок.

    Args:
        df: DataFrame для проверки
        expected_cols: Множество ожидаемых колонок

    Returns:
        Словарь с результатами проверки
    """
    actual_cols = set(df.columns)

    extra = sorted(actual_cols - expected_cols)
    missing = sorted(expected_cols - actual_cols)
    common = sorted(actual_cols & expected_cols)

    result = {
        "extra_cols": extra,
        "missing_cols": missing,
        "common_cols": common,
        "schema_match": len(extra) == 0 and len(missing) == 0,
        "coverage_rate": len(common) / len(expected_cols) if expected_cols else 0,
    }

    logger.info(
        f"Schema check: extra={extra}, missing={missing}, coverage={result['coverage_rate']:.1%}"
    )

    return result


def validate_schema_compat(records, expected_cols):
    """Валидация совместимости схемы перед вставкой"""
    if not records:
        return True
    keys = set().union(*(r.keys() for r in records))
    sorted(keys - set(expected_cols))
    missing = sorted(set(expected_cols) - keys)
    return not missing


def diagnose_df(df):
    """Диагностика DataFrame на лету"""
    num = df.select_dtypes(include=[np.number]).columns
    obj = df.select_dtypes(include=["object"]).columns
    return {
        "shape": df.shape,
        "object_cols": list(obj),
        "inf_total": int(np.isinf(df[num]).to_numpy().sum()) if len(num) else 0,
        "nan_total": int(df.isna().to_numpy().sum()),
    }


def diagnose_dataframe_issues(df: pd.DataFrame) -> dict[str, Any]:
    """
    Диагностирует потенциальные проблемы с DataFrame перед вставкой.

    Returns:
        Словарь с диагностической информацией
    """
    issues = []

    # Проверка типов данных
    object_cols = df.select_dtypes(include=["object"]).columns
    if len(object_cols) > 0:
        issues.append(f"Object columns found: {list(object_cols)}")

    # Проверка inf значений
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    inf_count = 0
    for col in numeric_cols:
        inf_count += np.isinf(df[col]).sum()
    if inf_count > 0:
        issues.append(f"Inf values found: {inf_count} total")

    # Проверка NaN значений
    nan_count = df.isna().sum().sum()
    if nan_count > 0:
        issues.append(f"NaN values found: {nan_count} total")

    result = {
        "issues": issues,
        "object_cols": list(object_cols),
        "inf_count": inf_count,
        "nan_count": nan_count,
        "shape": df.shape,
        "dtypes": df.dtypes.to_dict(),
    }

    logger.info(f"DataFrame diagnosis: {result}")
    return result
