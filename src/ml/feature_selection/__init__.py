"""
Отбор и оценка важности признаков.

Модули:
    importance — MDI, MDA, SFI feature importance (Блок E).
    reduction  — PCA / mutual info / MDA отбор признаков (Блок E).
"""

from src.ml.feature_selection.importance import (
    mda_importance,
    mdi_importance,
    sfi_importance,
)
from src.ml.feature_selection.reduction import select_features

__all__ = [
    "mda_importance",
    "mdi_importance",
    "select_features",
    "sfi_importance",
]
