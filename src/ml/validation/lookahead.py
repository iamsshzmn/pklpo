"""
Look-Ahead Bias Detector (AFML quality gate).

Обнаруживает look-ahead bias в pipeline с помощью детерминированного теста:

Алгоритм:
  1. Запустить pipeline на полном датасете df_full → result_A.
  2. Запустить pipeline на усечённом датасете df_full.iloc[:-n_trim] → result_B.
  3. Найти пересечение временных меток (intersection of indices).
  4. Сравнить результаты на общих timestamp — должны совпасть с точностью atol.

Если результаты различаются: pipeline использует данные из будущего (look-ahead bias).

Применение в CI:
  - Пометить тесты @pytest.mark.lookahead
  - Добавить шаг ``pytest -m lookahead`` как обязательный gate перед деплоем

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.7, 12
           (обсуждение необходимости проверки look-ahead в production-системах)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class LookaheadResult:
    """
    Результат проверки look-ahead bias.

    Attributes:
        passed:    True если pipeline не имеет look-ahead bias.
        max_diff:  Максимальное абсолютное расхождение между result_A и result_B
                   на общих временных метках. 0.0 если полное совпадение.
        n_compared: Число временных меток, использованных для сравнения.
        details:   Словарь с дополнительной диагностикой.
    """

    passed: bool
    max_diff: float
    n_compared: int
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"LookaheadResult({status}, "
            f"max_diff={self.max_diff:.2e}, "
            f"n_compared={self.n_compared})"
        )


def check_lookahead(
    pipeline_fn: Callable[[pd.DataFrame], pd.Series | pd.DataFrame],
    df_full: pd.DataFrame,
    n_trim: int = 100,
    atol: float = 1e-6,
) -> LookaheadResult:
    """
    Проверяет pipeline на отсутствие look-ahead bias.

    Запускает pipeline дважды — на полных и усечённых данных — и сравнивает
    результаты на общих временных метках.

    Args:
        pipeline_fn: Callable[[df], result] — pipeline для проверки.
                     Принимает pd.DataFrame (OHLCV или features),
                     возвращает pd.Series или pd.DataFrame с DatetimeIndex.
        df_full:     Полный датасет. Должен иметь DatetimeIndex.
        n_trim:      Число строк, обрезаемых с конца при втором прогоне.
                     Должно быть < len(df_full).
        atol:        Абсолютная погрешность при сравнении числовых значений.

    Returns:
        LookaheadResult с passed=True если bias не обнаружен.

    Raises:
        ValueError: если n_trim >= len(df_full) или < 1.
        ValueError: если pipeline_fn возвращает объект без DatetimeIndex.

    Example::

        def my_pipeline(df: pd.DataFrame) -> pd.Series:
            return df["close"].rolling(20).mean()

        result = check_lookahead(my_pipeline, df_ohlcv, n_trim=50)
        assert result.passed, str(result)
    """
    n = len(df_full)
    if not 1 <= n_trim < n:
        raise ValueError(
            f"n_trim={n_trim} должен быть в [1, {n - 1}] (len(df_full)={n})."
        )

    # Шаг 1: прогон на полных данных
    result_a: pd.Series | pd.DataFrame = pipeline_fn(df_full)

    # Шаг 2: прогон на усечённых данных
    df_trimmed = df_full.iloc[:-n_trim]
    result_b: pd.Series | pd.DataFrame = pipeline_fn(df_trimmed)

    # Проверка типов
    if not isinstance(result_a.index, pd.DatetimeIndex):
        raise ValueError(
            "pipeline_fn должен возвращать объект с pd.DatetimeIndex. "
            f"Получен: {type(result_a.index).__name__}"
        )

    # Шаг 3: пересечение временных меток
    common_idx = result_a.index.intersection(result_b.index)
    n_compared = len(common_idx)

    if n_compared == 0:
        return LookaheadResult(
            passed=False,
            max_diff=float("inf"),
            n_compared=0,
            details={"reason": "Нет общих временных меток для сравнения."},
        )

    # Шаг 4: сравнение на общих метках
    a_aligned = result_a.loc[common_idx]
    b_aligned = result_b.loc[common_idx]

    max_diff = _compute_max_diff(a_aligned, b_aligned)
    passed = max_diff <= atol

    details: dict[str, Any] = {
        "n_full": n,
        "n_trimmed": n - n_trim,
        "n_common": n_compared,
        "atol": atol,
    }
    if not passed:
        details["max_diff_location"] = _find_diff_location(a_aligned, b_aligned, atol)

    return LookaheadResult(
        passed=passed,
        max_diff=max_diff,
        n_compared=n_compared,
        details=details,
    )


def _compute_max_diff(
    a: pd.Series | pd.DataFrame,
    b: pd.Series | pd.DataFrame,
) -> float:
    """
    Вычисляет максимальное абсолютное расхождение между a и b.

    Правила NaN:
      - Оба NaN → расхождение = 0 (оба «неизвестны» — согласие).
      - Один NaN, другой не NaN → расхождение = inf (полное несогласие;
        пайплайн на полных данных получил значение там, где пайплайн
        на усечённых данных не смог — признак look-ahead).
    """
    if isinstance(a, pd.Series):
        a_vals = a.to_numpy(dtype=float, na_value=np.nan)
        b_vals = b.to_numpy(dtype=float, na_value=np.nan)
        diff = np.abs(a_vals - b_vals)
        # Оба NaN → не расхождение
        both_nan = np.isnan(a_vals) & np.isnan(b_vals)
        diff[both_nan] = 0.0
        # Ровно один NaN → полное расхождение (inf)
        one_nan = np.isnan(a_vals) ^ np.isnan(b_vals)
        diff[one_nan] = np.inf
        if len(diff) == 0:
            return 0.0
        finite_max = float(np.nanmax(np.where(np.isinf(diff), np.nan, diff)))
        return float("inf") if np.any(one_nan) else finite_max
    # DataFrame: проверяем числовые колонки
    a_df = a.select_dtypes(include=[np.number])
    b_df = b.select_dtypes(include=[np.number])
    if a_df.empty:
        return 0.0
    diff = (a_df - b_df).abs()
    return float(diff.max().max())


def _find_diff_location(
    a: pd.Series | pd.DataFrame,
    b: pd.Series | pd.DataFrame,
    atol: float,
) -> dict[str, Any]:
    """Возвращает первую временную метку с расхождением > atol."""
    if isinstance(a, pd.Series):
        a_vals = a.to_numpy(dtype=float, na_value=np.nan)
        b_vals = b.to_numpy(dtype=float, na_value=np.nan)
        diff = np.abs(a_vals - b_vals)
        diff = np.nan_to_num(diff, nan=0.0)
        where_bad = np.where(diff > atol)[0]
        if len(where_bad) > 0:
            idx = where_bad[0]
            ts = a.index[idx]
            return {
                "first_diff_ts": str(ts),
                "a_value": float(a_vals[idx]),
                "b_value": float(b_vals[idx]),
                "diff": float(diff[idx]),
            }
    return {}
