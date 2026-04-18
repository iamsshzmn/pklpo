"""
Common domain models for the ml module.

All dataclasses are frozen=True for immutability.
MetaScorer — Protocol for integrating metalabeling with the signals pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd


@dataclass(frozen=True)
class BarrierConfig:
    """
    Configuration for triple-barrier labeling.

    Attributes:
        profit_take: Upper barrier as a price fraction (e.g., 0.02 = 2%).
        stop_loss: Lower barrier as a price fraction (e.g., 0.01 = 1%).
        max_horizon: Maximum number of bars until the vertical barrier.
    """

    profit_take: float
    stop_loss: float
    max_horizon: int

    def __post_init__(self) -> None:
        if self.profit_take <= 0:
            raise ValueError(f"profit_take must be > 0, got {self.profit_take}")
        if self.stop_loss <= 0:
            raise ValueError(f"stop_loss must be > 0, got {self.stop_loss}")
        if self.max_horizon < 1:
            raise ValueError(f"max_horizon must be >= 1, got {self.max_horizon}")


@dataclass(frozen=True)
class LabelResult:
    """
    Result of triple-barrier labeling for a single bar.

    Attributes:
        label: Direction label: +1 (profit take), -1 (stop loss), 0 (vertical barrier).
        t1: Timestamp when the barrier was triggered.
        barrier_type: Type of barrier triggered: "pt", "sl", or "vert".
    """

    label: int
    t1: pd.Timestamp
    barrier_type: str

    def __post_init__(self) -> None:
        if self.label not in (-1, 0, 1):
            raise ValueError(f"label must be -1, 0 or +1, got {self.label}")
        if self.barrier_type not in ("pt", "sl", "vert"):
            raise ValueError(
                f"barrier_type must be 'pt', 'sl' or 'vert', got {self.barrier_type}"
            )


class MetaScorer(Protocol):
    """
    Protocol for integrating a metalabeling model with the signals pipeline.

    Allows src/signals/decision/maker.py to accept any MetaLabeler implementation
    without a direct dependency on the concrete class.
    """

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Returns a probability matrix for each class.

        Args:
            X: Feature matrix, shape (n_samples, n_features).

        Returns:
            np.ndarray: Probability matrix, shape (n_samples, n_classes).
        """
        ...
