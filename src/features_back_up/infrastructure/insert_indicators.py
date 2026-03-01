"""
Compatibility shim for the refactored insert_indicators module.

This module re-exports the public API from the `src.features.infrastructure.persistence` package
to maintain backward compatibility with existing imports.
"""

from .persistence import insert_indicators

__all__ = ["insert_indicators"]
