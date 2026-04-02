"""Ports for pluggable feature-calculation backend selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd

FeatureBackendId = Literal["auto", "talib", "pandas_ta", "python", "fallback"]


@runtime_checkable
class FeatureCalculatorBackend(Protocol):
    """Strategy contract for wrapping feature calculation with a TA backend."""

    backend_id: FeatureBackendId

    def __call__(
        self,
        compute_fn: Callable[..., pd.DataFrame],
        df_ohlcv: pd.DataFrame,
        specs: list[str] | None = None,
        *,
        volatility_normalize: bool = False,
        normalize_window: int = 20,
        **kwargs,
    ) -> pd.DataFrame: ...


__all__ = ["FeatureBackendId", "FeatureCalculatorBackend"]
