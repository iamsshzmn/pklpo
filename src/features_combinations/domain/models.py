"""Домейн-модели для комбинаций фичей."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(slots=True)
class CombinationRow:
    """
    Модель строки комбинации фичей.

    Хранит только числовые фичи в features, без текстовых рекомендаций.
    Все "направления" и "сигналы" кодируются числами (например, direction_num: -1|0|1).
    """

    symbol: str
    timeframe: str
    timestamp: datetime | int  # datetime или epoch_ms (int)
    combination_id: str

    features: dict[str, float]  # только числа
    meta: dict[str, Any] | None = None
