"""Minimal compatibility facade for the `src.candles` bounded context."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import load_instruments as load_instruments

__all__ = ["load_instruments"]


def __getattr__(name: str) -> object:
    if name == "load_instruments":
        return import_module(f"{__name__}.load_instruments")
    raise AttributeError(name)
