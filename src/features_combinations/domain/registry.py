#!/usr/bin/env python3
"""
Централизованный реестр комбинаций индикаторов и их схемы.
"""

from typing import TypedDict

from .pairs import PAIRS
from .quartets import QUARTETS
from .trios import TRIOS


class CombinationConfig(TypedDict):
    indicators: list[str]
    roles: list[str]
    description: str


# Единый источник правды для комбинаций
COMBINATIONS: dict[str, CombinationConfig] = {**PAIRS, **TRIOS, **QUARTETS}
