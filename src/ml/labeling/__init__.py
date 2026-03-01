"""
Маркировка данных для обучения ML-моделей.

Модули:
    triple_barrier  — Triple-barrier маркировка (numba JIT + Python fallback).
    sample_weights  — Uniqueness-based sample weights (AFML Ch.4).
"""

from src.ml.labeling.sample_weights import get_uniqueness_weights
from src.ml.labeling.triple_barrier import triple_barrier_labels

__all__ = ["get_uniqueness_weights", "triple_barrier_labels"]
