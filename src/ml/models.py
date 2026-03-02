"""
Общие domain-модели для ml-модуля.

Все dataclasses frozen=True для иммутабельности.
MetaScorer — Protocol для интеграции metalabeling с signals pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BarrierConfig:
    """
    Конфигурация triple-barrier маркировки.

    Attributes:
        profit_take: Верхний барьер как доля цены (например, 0.02 = 2%).
        stop_loss: Нижний барьер как доля цены (например, 0.01 = 1%).
        max_horizon: Максимальное число баров до вертикального барьера.
    """

    profit_take: float
    stop_loss: float
    max_horizon: int

    def __post_init__(self) -> None:
        if self.profit_take <= 0:
            raise ValueError(f"profit_take должен быть > 0, получен {self.profit_take}")
        if self.stop_loss <= 0:
            raise ValueError(f"stop_loss должен быть > 0, получен {self.stop_loss}")
        if self.max_horizon < 1:
            raise ValueError(f"max_horizon должен быть >= 1, получен {self.max_horizon}")


@dataclass(frozen=True)
class LabelResult:
    """
    Результат triple-barrier маркировки для одного бара.

    Attributes:
        label: Метка направления: +1 (profit take), -1 (stop loss), 0 (вертикальный барьер).
        t1: Timestamp срабатывания барьера.
        barrier_type: Тип сработавшего барьера: "pt", "sl" или "vert".
    """

    label: int
    t1: pd.Timestamp
    barrier_type: str

    def __post_init__(self) -> None:
        if self.label not in (-1, 0, 1):
            raise ValueError(f"label должен быть -1, 0 или +1, получен {self.label}")
        if self.barrier_type not in ("pt", "sl", "vert"):
            raise ValueError(
                f"barrier_type должен быть 'pt', 'sl' или 'vert', получен {self.barrier_type}"
            )


class MetaScorer(Protocol):
    """
    Protocol для интеграции metalabeling-модели с signals pipeline.

    Позволяет src/signals/decision/maker.py принимать любую реализацию
    MetaLabeler без прямой зависимости от конкретного класса.
    """

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Возвращает матрицу вероятностей для каждого класса.

        Args:
            X: Матрица признаков, форма (n_samples, n_features).

        Returns:
            np.ndarray: Матрица вероятностей, форма (n_samples, n_classes).
        """
        ...
