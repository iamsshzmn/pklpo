from __future__ import annotations

from dataclasses import dataclass

from src.features.specs import FEATURE_SPECS

OPERATIONAL_MIN_BARS = 280
RECOMMENDED_BARS = 500
CUMULATIVE_FEATURE_NAMES = frozenset({"ad", "obv", "vwap"})
LOOKAHEAD_FEATURE_NAMES = frozenset[str]()


@dataclass(frozen=True)
class WarmupContract:
    raw_min_bars: int
    operational_min_bars: int
    recommended_bars: int
    feature_requirements: dict[str, int]
    cumulative_features: frozenset[str]
    lookahead_features: frozenset[str]
    unclassified_features: frozenset[str]


def build_warmup_contract() -> WarmupContract:
    feature_requirements = {
        name: _raw_requirement_from_spec(name, spec.params)
        for name, spec in FEATURE_SPECS.items()
    }
    raw_min_bars = max(feature_requirements.values(), default=1)
    cumulative_features = frozenset(
        name for name in CUMULATIVE_FEATURE_NAMES if name in FEATURE_SPECS
    )
    lookahead_features = frozenset(
        name for name in LOOKAHEAD_FEATURE_NAMES if name in FEATURE_SPECS
    )
    return WarmupContract(
        raw_min_bars=raw_min_bars,
        operational_min_bars=max(raw_min_bars, OPERATIONAL_MIN_BARS),
        recommended_bars=RECOMMENDED_BARS,
        feature_requirements=feature_requirements,
        cumulative_features=cumulative_features,
        lookahead_features=lookahead_features,
        unclassified_features=frozenset(),
    )


def _raw_requirement_from_spec(name: str, params: dict[str, object]) -> int:
    numeric_periods = [
        int(value)
        for key, value in params.items()
        if _is_period_key(key) and isinstance(value, int | float)
    ]
    if numeric_periods:
        return max(1, max(numeric_periods))
    if name in CUMULATIVE_FEATURE_NAMES:
        return 1
    return 1


def _is_period_key(key: str) -> bool:
    return (
        key == "period"
        or key.endswith("_period")
        or key
        in {
            "length",
            "window",
            "fast",
            "slow",
            "signal",
        }
    )
