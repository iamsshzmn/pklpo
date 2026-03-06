"""Backward-compatible metrics shim for legacy tests/import sites."""

from __future__ import annotations

from .observability.metrics import *  # noqa: F403

__all__ = [name for name in globals() if not name.startswith("_")]
