"""
Infrastructure wrapper over legacy registry package.

Цель: предоставить стабильную точку доступа к реестру индикаторов,
не меняя поведение. На данном шаге просто реэкспортируем из registry/.
"""

from __future__ import annotations

from ..registry import AVAILABLE_INDICATORS, INDICATOR_CONFIG  # re-export

__all__ = [
    "AVAILABLE_INDICATORS",
    "INDICATOR_CONFIG",
]
