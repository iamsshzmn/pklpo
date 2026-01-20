"""
Validation functions for ta_safe module.
"""

import logging

import pandas as pd

from .constants import REQ
from .errors import FeatureCalcError

logger = logging.getLogger(__name__)


def _ensure_input(df: pd.DataFrame) -> None:
    """
    Проверка входных данных.

    Args:
        df: DataFrame для проверки

    Raises:
        FeatureCalcError: Если отсутствуют обязательные колонки или DataFrame пустой
    """
    miss = [c for c in REQ if c not in df.columns]
    if miss:
        raise FeatureCalcError(f"нет колонок: {miss}")
    if df.empty:
        raise FeatureCalcError("пустой DataFrame")


def _validate_allowlist(allow: set[str]) -> None:
    """
    Проверка доступности функций из ALLOW при загрузке модуля.

    Примечание: функции trange, tr, cdl_doji, cdl_inside исключены из пайплайна.
    - tr/trange: ATR считает True Range внутри себя
    - cdl_doji/cdl_inside: используют собственные реализации в candles.py

    Args:
        allow: Множество разрешенных функций
    """
    try:
        accessor = pd.DataFrame().ta
    except Exception as e:
        logger.warning(f"pandas_ta не активен: df.ta недоступен: {e}")
        return
    missing = [n for n in allow if getattr(accessor, n, None) is None]
    if missing:
        logger.debug(
            f"В pandas_ta нет функций: {missing}. "
            "Эти функции либо исключены из пайплайна, либо используют fallback."
        )
