"""
Metalabeling pipeline для фильтрации торговых сигналов.

Модули:
    pipeline    — MetaLabeler: fit/predict_proba с feature selection (Блок F).
    calibration — CalibratedMetaLabeler: Brier score + reliability curve (Блок F).
"""

from src.ml.metalabeling.calibration import CalibratedMetaLabeler
from src.ml.metalabeling.pipeline import MetaLabeler

__all__ = [
    "CalibratedMetaLabeler",
    "MetaLabeler",
]
