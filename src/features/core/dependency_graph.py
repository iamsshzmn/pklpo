"""
Dependency graph management using NetworkX.

This module provides utilities for building and resolving feature dependencies
dynamically, enabling parallel calculation of independent features.
"""

from collections import defaultdict
from typing import Any

try:
    import networkx as nx  # type: ignore[import-untyped]

    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None


# =============================================================================
# GROUP-LEVEL DEPENDENCY RESOLUTION
# =============================================================================


def resolve_group_order(group_deps: dict[str, list[str]]) -> list[str]:
    """
           .

     source of truth    —
     GROUP_METADATA.   hardcoded linear fallback-order.

    Args:
        group_deps: dict  {"group_name": ["dep1", "dep2"], ...}
                     —  ;  —  .

    Returns:
              .

    Raises:
        ImportError:  networkx  .
        ValueError:     .

    Example:
        >>> deps = {
        ...     "overlap": [],
        ...     "ma": ["overlap"],
        ...     "oscillators": ["overlap", "ma"],
        ... }
        >>> resolve_group_order(deps)
        ['overlap', 'ma', 'oscillators']
    """
    if not NETWORKX_AVAILABLE or nx is None:
        raise ImportError(
            "networkx is required for resolve_group_order(). "
            "Install it: pip install networkx"
        )

    dag: Any = nx.DiGraph()

    # Add all groups as nodes
    for group in group_deps:
        dag.add_node(group)

    # Add dependency edges: dep -> group (dep must run before group)
    for group, deps in group_deps.items():
        for dep in deps:
            if dep not in dag:
                dag.add_node(dep)
            dag.add_edge(dep, group)

    # Detect cycles
    if not nx.is_directed_acyclic_graph(dag):
        cycles = list(nx.simple_cycles(dag))
        raise ValueError(f"Circular dependency detected in group_deps: {cycles}")

    return list(nx.topological_sort(dag))


from src.logging import get_features_logger

from ..domain.models import FeatureSpec

logger = get_features_logger("features.dependency_graph")


class DependencyGraphError(Exception):
    """Exception raised for dependency graph errors."""

    pass


class FeatureDependencyGraph:
    """
    Manages feature dependencies using a directed acyclic graph (DAG).

    Features can depend on OHLCV columns and other features.
    The graph ensures no circular dependencies and provides topological ordering.
    """

    def __init__(self) -> None:
        """Initialize the dependency graph."""
        if not NETWORKX_AVAILABLE:
            logger.warning("NetworkX not installed. Using fallback implementation.")
            self.graph: Any = None
            self.fallback_mode = True
        else:
            self.graph = nx.DiGraph()
            self.fallback_mode = False

        self.features: dict[str, FeatureSpec] = {}
        self.logger = get_features_logger("features.dependency_graph")

    def add_feature(self, spec: FeatureSpec) -> None:
        """
        Add a feature to the dependency graph.

        Args:
            spec: Feature specification

        Raises:
            DependencyGraphError: If adding the feature creates a cycle
        """
        self.features[spec.name] = spec

        if self.fallback_mode:
            return

        # Add feature node
        self.graph.add_node(spec.name, spec=spec, type="feature")

        # Add OHLCV dependencies
        for col in spec.requires:
            if not self.graph.has_node(col):
                self.graph.add_node(col, type="ohlcv")
            self.graph.add_edge(col, spec.name)

        # Add feature dependencies
        if spec.dependencies:
            for dep in spec.dependencies:
                if not self.graph.has_node(dep):
                    self.graph.add_node(dep, type="feature")
                self.graph.add_edge(dep, spec.name)

        # Check for cycles
        if not nx.is_directed_acyclic_graph(self.graph):
            self.graph.remove_node(spec.name)
            raise DependencyGraphError(
                f"Adding feature '{spec.name}' creates a circular dependency"
            )

        self.logger.debug(
            f"Added feature '{spec.name}' with {len(spec.requires)} OHLCV deps "
            f"and {len(spec.dependencies or [])} feature deps"
        )

    def get_calculation_order(self, features: list[str] | None = None) -> list[str]:
        """
        Get topological order for feature calculation.

        Args:
            features: Specific features to calculate (None = all features)

        Returns:
            List of feature names in calculation order

        Raises:
            DependencyGraphError: If graph has cycles or missing dependencies
        """
        if self.fallback_mode:
            return self._get_fallback_order(features)

        # If specific features requested, create subgraph
        if features:
            nodes_to_include = set(features)
            # Add all ancestors (dependencies)
            for feature in features:
                if feature in self.graph:
                    nodes_to_include.update(nx.ancestors(self.graph, feature))

            subgraph = self.graph.subgraph(nodes_to_include)
        else:
            subgraph = self.graph

        # Get topological order
        try:
            order = list(nx.topological_sort(subgraph))
        except nx.NetworkXError as e:
            raise DependencyGraphError(
                f"Failed to compute calculation order: {e}"
            ) from e

        # Filter out OHLCV nodes, keep only features
        feature_order = [
            node for node in order if self.graph.nodes[node].get("type") == "feature"
        ]

        self.logger.info(
            f"Calculated order for {len(feature_order)} features: "
            f"{', '.join(feature_order[:5])}{'...' if len(feature_order) > 5 else ''}"
        )

        return feature_order

    def get_parallel_batches(
        self, features: list[str] | None = None
    ) -> list[list[str]]:
        """
        Group features into batches that can be calculated in parallel.

        Features in the same batch have no dependencies on each other.

        Args:
            features: Specific features to calculate (None = all features)

        Returns:
            List of batches, where each batch is a list of feature names
        """
        if self.fallback_mode:
            # Fallback: return single batch
            order = self._get_fallback_order(features)
            return [[f] for f in order]

        order = self.get_calculation_order(features)

        if not order:
            return []

        # Group by generation (distance from OHLCV nodes)
        generations: dict[int, list[str]] = defaultdict(list)

        for feature in order:
            # Calculate generation as max distance from any OHLCV node
            ohlcv_nodes = [
                node
                for node in self.graph.nodes
                if self.graph.nodes[node].get("type") == "ohlcv"
            ]

            max_distance = 0
            for ohlcv_node in ohlcv_nodes:
                if nx.has_path(self.graph, ohlcv_node, feature):
                    distance = nx.shortest_path_length(self.graph, ohlcv_node, feature)
                    max_distance = max(max_distance, distance)

            generations[max_distance].append(feature)

        # Convert to list of batches
        batches = [generations[gen] for gen in sorted(generations.keys())]

        self.logger.info(
            f"Created {len(batches)} parallel batches. "
            f"Sizes: {[len(b) for b in batches]}"
        )

        return batches

    def _get_fallback_order(self, features: list[str] | None = None) -> list[str]:
        """
        Fallback calculation order when NetworkX is not available.

        Uses predefined group ordering.
        """
        GROUP_ORDER = [
            "overlap",
            "ma",
            "oscillators",
            "volatility",
            "volume",
            "trend",
            "candles",
            "squeeze",
            "statistics",
            "performance",
        ]

        if features is None:
            features = list(self.features.keys())

        # Group features by type
        grouped: dict[str, list[str]] = defaultdict(list)
        for fname in features:
            if fname in self.features:
                ftype = self.features[fname].type
                grouped[ftype].append(fname)

        # Order by group
        order = []
        for group in GROUP_ORDER:
            if group in grouped:
                order.extend(sorted(grouped[group]))

        self.logger.warning(
            f"Using fallback ordering for {len(order)} features "
            "(install networkx for dynamic dependency resolution)"
        )

        return order

    def validate_dependencies(self) -> tuple[bool, list[str]]:
        """
        Validate all feature dependencies.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        for fname, spec in self.features.items():
            # Check if feature dependencies exist
            if spec.dependencies:
                for dep in spec.dependencies:
                    if dep not in self.features:
                        errors.append(
                            f"Feature '{fname}' depends on unknown feature '{dep}'"
                        )

        if self.fallback_mode:
            return (len(errors) == 0, errors)

        # Check for cycles (should not happen if add_feature works correctly)
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            for cycle in cycles:
                errors.append(f"Circular dependency detected: {' -> '.join(cycle)}")

        return (len(errors) == 0, errors)

    def get_dependencies(self, feature: str) -> set[str]:
        """
        Get all dependencies (direct and transitive) for a feature.

        Args:
            feature: Feature name

        Returns:
            Set of feature names that this feature depends on
        """
        if self.fallback_mode:
            if feature in self.features:
                return set(self.features[feature].dependencies or [])
            return set()

        if feature not in self.graph:
            return set()

        ancestors = nx.ancestors(self.graph, feature)
        # Filter out OHLCV nodes
        return {
            node
            for node in ancestors
            if self.graph.nodes[node].get("type") == "feature"
        }

    def get_dependents(self, feature: str) -> set[str]:
        """
        Get all features that depend on this feature.

        Args:
            feature: Feature name

        Returns:
            Set of feature names that depend on this feature
        """
        if self.fallback_mode:
            dependents = set()
            for fname, spec in self.features.items():
                if spec.dependencies and feature in spec.dependencies:
                    dependents.add(fname)
            return dependents

        if feature not in self.graph:
            return set()

        descendants = nx.descendants(self.graph, feature)
        # Filter out non-feature nodes
        return {
            node
            for node in descendants
            if self.graph.nodes[node].get("type") == "feature"
        }


def build_dependency_graph(
    feature_specs: dict[str, FeatureSpec],
) -> FeatureDependencyGraph:
    """
    Build a dependency graph from feature specifications.

    Args:
        feature_specs: Dictionary mapping feature names to FeatureSpec objects

    Returns:
        Configured FeatureDependencyGraph

    Raises:
        DependencyGraphError: If graph construction fails
    """
    graph = FeatureDependencyGraph()

    for spec in feature_specs.values():
        try:
            graph.add_feature(spec)
        except DependencyGraphError as e:
            logger.error(f"Failed to add feature '{spec.name}' to graph: {e}")
            raise

    # Validate the complete graph
    is_valid, errors = graph.validate_dependencies()
    if not is_valid:
        error_msg = "Dependency validation failed:\n" + "\n".join(errors)
        raise DependencyGraphError(error_msg)

    logger.info(f"Built dependency graph with {len(feature_specs)} features")

    return graph
