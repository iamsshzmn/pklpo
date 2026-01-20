"""Domain layer для features_combinations."""

from .models import CombinationRow
from .registry import COMBINATIONS, CombinationConfig

__all__ = ["CombinationRow", "COMBINATIONS", "CombinationConfig"]
