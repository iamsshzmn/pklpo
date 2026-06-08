#!/usr/bin/env python3
"""
Централизованный реестр комбинаций индикаторов и их схемы.
"""

from typing import Any, TypedDict, cast

from .pairs import PAIRS
from .quartets import QUARTETS
from .trios import TRIOS


class CombinationConfig(TypedDict):
    indicators: list[str]
    roles: list[str]
    description: str


# Единый источник правды для комбинаций
COMBINATIONS: dict[str, CombinationConfig] = cast(
    "dict[str, CombinationConfig]",
    {
        **cast("dict[str, Any]", PAIRS),
        **cast("dict[str, Any]", TRIOS),
        **cast("dict[str, Any]", QUARTETS),
    },
)
