"""
Tests for dependency graph module.
"""

import pytest

from ..core.dependency_graph import (
    NETWORKX_AVAILABLE,
    DependencyGraphError,
    FeatureDependencyGraph,
    build_dependency_graph,
)
from ..domain.models import FeatureSpec


class TestFeatureDependencyGraph:
    """Tests for FeatureDependencyGraph class."""

    def test_add_feature_simple(self):
        """Test adding a simple feature with no dependencies."""
        graph = FeatureDependencyGraph()

        spec = FeatureSpec(
            name="sma_20",
            type="ma",
            params={"period": 20},
            requires=["close"],
            description="Simple Moving Average 20",
        )

        graph.add_feature(spec)

        assert "sma_20" in graph.features
        assert graph.features["sma_20"] == spec

    def test_add_feature_with_dependencies(self):
        """Test adding a feature that depends on another feature."""
        graph = FeatureDependencyGraph()

        # Add base feature first
        sma_spec = FeatureSpec(
            name="sma_20",
            type="ma",
            params={"period": 20},
            requires=["close"],
            description="SMA 20",
        )
        graph.add_feature(sma_spec)

        # Add dependent feature
        bb_spec = FeatureSpec(
            name="bb_upper",
            type="volatility",
            params={"period": 20, "std_dev": 2},
            requires=["close"],
            dependencies=["sma_20"],
            description="Bollinger Band Upper",
        )
        graph.add_feature(bb_spec)

        assert "bb_upper" in graph.features
        assert "sma_20" in graph.features

    def test_get_calculation_order_simple(self):
        """Test getting calculation order for simple features."""
        graph = FeatureDependencyGraph()

        specs = [
            FeatureSpec("sma_20", "ma", {"period": 20}, ["close"], "SMA 20"),
            FeatureSpec("ema_12", "ma", {"period": 12}, ["close"], "EMA 12"),
            FeatureSpec("rsi_14", "oscillator", {"period": 14}, ["close"], "RSI 14"),
        ]

        for spec in specs:
            graph.add_feature(spec)

        order = graph.get_calculation_order()

        # All three should be in the order
        assert len(order) == 3
        assert set(order) == {"sma_20", "ema_12", "rsi_14"}

    @pytest.mark.skipif(not NETWORKX_AVAILABLE, reason="NetworkX not installed")
    def test_get_calculation_order_with_dependencies(self):
        """Test calculation order respects dependencies."""
        graph = FeatureDependencyGraph()

        # Add features with dependencies
        sma_spec = FeatureSpec("sma_20", "ma", {"period": 20}, ["close"], "SMA 20")
        bb_spec = FeatureSpec(
            "bb_upper",
            "volatility",
            {"period": 20},
            ["close"],
            "BB Upper",
            dependencies=["sma_20"],
        )
        macd_spec = FeatureSpec(
            "macd",
            "oscillator",
            {},
            ["close"],
            "MACD",
            dependencies=["ema_12", "ema_26"],
        )
        ema12_spec = FeatureSpec("ema_12", "ma", {"period": 12}, ["close"], "EMA 12")
        ema26_spec = FeatureSpec("ema_26", "ma", {"period": 26}, ["close"], "EMA 26")

        for spec in [sma_spec, bb_spec, macd_spec, ema12_spec, ema26_spec]:
            graph.add_feature(spec)

        order = graph.get_calculation_order()

        # SMA must come before BB
        sma_idx = order.index("sma_20")
        bb_idx = order.index("bb_upper")
        assert sma_idx < bb_idx

        # EMAs must come before MACD
        ema12_idx = order.index("ema_12")
        ema26_idx = order.index("ema_26")
        macd_idx = order.index("macd")
        assert ema12_idx < macd_idx
        assert ema26_idx < macd_idx

    @pytest.mark.skipif(not NETWORKX_AVAILABLE, reason="NetworkX not installed")
    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        graph = FeatureDependencyGraph()

        # Add feature A
        spec_a = FeatureSpec(
            "feature_a", "trend", {}, ["close"], "Feature A", dependencies=["feature_b"]
        )

        # Add feature B that depends on A (circular)
        spec_b = FeatureSpec(
            "feature_b", "trend", {}, ["close"], "Feature B", dependencies=["feature_a"]
        )

        # Should raise error when adding creates cycle
        with pytest.raises(DependencyGraphError):
            graph.add_feature(spec_a)
            graph.add_feature(spec_b)

    def test_get_dependencies(self):
        """Test getting all dependencies for a feature."""
        graph = FeatureDependencyGraph()

        ema_spec = FeatureSpec("ema_12", "ma", {"period": 12}, ["close"], "EMA 12")
        macd_spec = FeatureSpec(
            "macd",
            "oscillator",
            {},
            ["close"],
            "MACD",
            dependencies=["ema_12", "ema_26"],
        )

        graph.add_feature(ema_spec)
        graph.add_feature(macd_spec)

        deps = graph.get_dependencies("macd")

        assert "ema_12" in deps

    @pytest.mark.skipif(not NETWORKX_AVAILABLE, reason="NetworkX not installed")
    def test_get_parallel_batches(self):
        """Test grouping features into parallel batches."""
        graph = FeatureDependencyGraph()

        # Add independent features
        specs = [
            FeatureSpec("sma_20", "ma", {}, ["close"], "SMA 20"),
            FeatureSpec("ema_12", "ma", {}, ["close"], "EMA 12"),
            FeatureSpec("rsi_14", "oscillator", {}, ["close"], "RSI 14"),
        ]

        for spec in specs:
            graph.add_feature(spec)

        batches = graph.get_parallel_batches()

        # All independent features should be in first batch
        assert len(batches) >= 1
        assert len(batches[0]) == 3

    def test_validate_dependencies_success(self):
        """Test validation succeeds for valid graph."""
        graph = FeatureDependencyGraph()

        sma_spec = FeatureSpec("sma_20", "ma", {}, ["close"], "SMA 20")
        bb_spec = FeatureSpec(
            "bb_upper", "volatility", {}, ["close"], "BB Upper", dependencies=["sma_20"]
        )

        graph.add_feature(sma_spec)
        graph.add_feature(bb_spec)

        is_valid, errors = graph.validate_dependencies()

        assert is_valid
        assert len(errors) == 0

    def test_validate_dependencies_missing(self):
        """Test validation fails for missing dependency."""
        graph = FeatureDependencyGraph()

        # Add feature with missing dependency
        bb_spec = FeatureSpec(
            "bb_upper",
            "volatility",
            {},
            ["close"],
            "BB Upper",
            dependencies=["sma_20"],  # sma_20 not added
        )

        graph.add_feature(bb_spec)

        is_valid, errors = graph.validate_dependencies()

        assert not is_valid
        assert len(errors) > 0
        assert "sma_20" in errors[0]


class TestBuildDependencyGraph:
    """Tests for build_dependency_graph function."""

    def test_build_simple_graph(self):
        """Test building graph from feature specs."""
        specs = {
            "sma_20": FeatureSpec("sma_20", "ma", {}, ["close"], "SMA 20"),
            "ema_12": FeatureSpec("ema_12", "ma", {}, ["close"], "EMA 12"),
        }

        graph = build_dependency_graph(specs)

        assert "sma_20" in graph.features
        assert "ema_12" in graph.features

    def test_build_graph_with_invalid_dependencies(self):
        """Test building graph with invalid dependencies fails."""
        specs = {
            "bb_upper": FeatureSpec(
                "bb_upper",
                "volatility",
                {},
                ["close"],
                "BB Upper",
                dependencies=["missing_feature"],
            )
        }

        with pytest.raises(DependencyGraphError):
            build_dependency_graph(specs)


@pytest.mark.skipif(NETWORKX_AVAILABLE, reason="Test fallback mode only")
class TestFallbackMode:
    """Tests for fallback mode when NetworkX is not installed."""

    def test_fallback_calculation_order(self):
        """Test fallback ordering works."""
        graph = FeatureDependencyGraph()

        specs = [
            FeatureSpec("trend_1", "trend", {}, ["close"], "Trend 1"),
            FeatureSpec("ma_1", "ma", {}, ["close"], "MA 1"),
            FeatureSpec("osc_1", "oscillator", {}, ["close"], "Osc 1"),
        ]

        for spec in specs:
            graph.add_feature(spec)

        order = graph.get_calculation_order()

        # MA should come before oscillators in fallback mode
        ma_idx = order.index("ma_1")
        osc_idx = order.index("osc_1")
        assert ma_idx < osc_idx
