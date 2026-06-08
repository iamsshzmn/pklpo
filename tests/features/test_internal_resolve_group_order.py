"""
Internal white-box tests for resolve_group_order().
"""

from __future__ import annotations

import pytest

try:
    import networkx  # noqa: F401

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not NETWORKX_AVAILABLE,
    reason="networkx required for resolve_group_order",
)


@pytest.fixture
def simple_deps():
    return {
        "overlap": [],
        "ma": ["overlap"],
        "oscillators": ["overlap", "ma"],
    }


@pytest.fixture
def full_group_deps():
    return {
        "overlap": [],
        "ma": ["overlap"],
        "oscillators": ["overlap", "ma"],
        "volatility": ["overlap", "ma"],
        "volume": ["overlap"],
        "trend": ["overlap", "ma"],
        "squeeze": ["volatility", "trend"],
        "candles": ["overlap"],
        "statistics": ["overlap", "ma"],
        "performance": ["overlap", "ma", "volatility"],
    }


def test_simple_order_respects_deps(simple_deps):
    from src.features.core.dependency_graph import resolve_group_order

    order = resolve_group_order(simple_deps)

    assert order.index("overlap") < order.index("ma")
    assert order.index("ma") < order.index("oscillators")
    assert order.index("overlap") < order.index("oscillators")


def test_all_groups_present(full_group_deps):
    from src.features.core.dependency_graph import resolve_group_order

    order = resolve_group_order(full_group_deps)

    assert set(order) == set(full_group_deps.keys())


def test_squeeze_after_volatility_and_trend(full_group_deps):
    from src.features.core.dependency_graph import resolve_group_order

    order = resolve_group_order(full_group_deps)

    assert order.index("squeeze") > order.index("volatility")
    assert order.index("squeeze") > order.index("trend")


def test_performance_after_volatility(full_group_deps):
    from src.features.core.dependency_graph import resolve_group_order

    order = resolve_group_order(full_group_deps)

    assert order.index("performance") > order.index("volatility")
    assert order.index("performance") > order.index("ma")


def test_independent_branches_all_included():
    from src.features.core.dependency_graph import resolve_group_order

    deps = {
        "overlap": [],
        "ma": ["overlap"],
        "volume": ["overlap"],
        "candles": ["overlap"],
    }
    order = resolve_group_order(deps)

    assert set(order) == {"overlap", "ma", "volume", "candles"}
    assert order.index("overlap") < order.index("ma")
    assert order.index("overlap") < order.index("volume")
    assert order.index("overlap") < order.index("candles")


def test_cycle_detection_raises():
    from src.features.core.dependency_graph import resolve_group_order

    deps = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a"],
    }
    with pytest.raises(ValueError, match=r"[Cc]ircular"):
        resolve_group_order(deps)


def test_adding_new_group_without_hardcoded_list():
    from src.features.core.dependency_graph import resolve_group_order

    deps = {
        "overlap": [],
        "ma": ["overlap"],
        "new_ml_group": ["ma"],
    }
    order = resolve_group_order(deps)

    assert "new_ml_group" in order
    assert order.index("new_ml_group") > order.index("ma")


def test_empty_deps_returns_empty():
    from src.features.core.dependency_graph import resolve_group_order

    assert resolve_group_order({}) == []


def test_single_group_no_deps():
    from src.features.core.dependency_graph import resolve_group_order

    order = resolve_group_order({"overlap": []})
    assert order == ["overlap"]


def test_overlap_always_first(full_group_deps):
    from src.features.core.dependency_graph import resolve_group_order

    order = resolve_group_order(full_group_deps)
    assert order[0] == "overlap"
