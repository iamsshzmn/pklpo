"""Legacy feature name mapping compatibility module."""

from .specs import FEATURE_SPECS

NAME_MAPPING: dict[str, str] = {name: name for name in FEATURE_SPECS}


def get_name_mapping() -> dict[str, str]:
    return dict(NAME_MAPPING)


def normalize_feature_name(name: str) -> str:
    return NAME_MAPPING.get(name, name)


__all__ = ["NAME_MAPPING", "get_name_mapping", "normalize_feature_name"]
