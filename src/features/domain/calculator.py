"""
Domain-level calculator facade.

Задача: предоставить тонкую обертку над compute_features без изменения поведения.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core import compute_features

if TYPE_CHECKING:
    import pandas as pd


def calculate_batch(
    df_ohlcv: pd.DataFrame,
    available: set[str] | None = None,
    specs: list[str] | None = None,
    volatility_normalize: bool = False,
) -> pd.DataFrame:
    """Выполнить расчет индикаторов для датафрейма OHLCV.

    Сохраняет текущее поведение: по умолчанию без нормализации волатильности.
    """
    return compute_features(
        df_ohlcv=df_ohlcv,
        available=available,
        specs=specs,
        volatility_normalize=volatility_normalize,
    )
