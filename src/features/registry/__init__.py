"""
Unified indicator registry derived from specs.

Exports:
- AVAILABLE_INDICATORS: list of indicator names
- INDICATOR_CONFIG: mapping name -> metadata (type, requires, params, dependencies, description)
"""

from __future__ import annotations

from typing import Any

from ..specs import FEATURE_SPECS

# Public API: list of all available indicator names (stable ordering for reproducibility)
AVAILABLE_INDICATORS: list[str] = sorted(FEATURE_SPECS.keys())


# Public API: per-indicator configuration extracted from FeatureSpec
INDICATOR_CONFIG: dict[str, dict[str, Any]] = {}
for name, spec in FEATURE_SPECS.items():
    INDICATOR_CONFIG[name] = {
        "type": spec.type,
        "requires": list(spec.requires),
        "params": dict(spec.params),
        "dependencies": (
            list(spec.dependencies) if getattr(spec, "dependencies", None) else []
        ),
        "description": spec.description,
    }


__all__ = ["AVAILABLE_INDICATORS", "INDICATOR_CONFIG"]
