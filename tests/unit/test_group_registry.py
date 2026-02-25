"""
Unit tests for GroupRegistry (Task 9).

Tests the decorator-based indicator group registration.
"""

from src.features.indicator_groups.registry import (
    GroupEntry,
    GroupRegistry,
    get_group_calculator,
    get_group_order,
    get_ordered_groups,
)


class TestGroupEntry:
    """Tests for GroupEntry dataclass."""

    def test_default_description(self):
        """GroupEntry creates default description."""
        entry = GroupEntry(
            name="test",
            calculator=lambda df, avail: {},
            order=1,
        )

        assert entry.description == "test indicator group"

    def test_custom_description(self):
        """GroupEntry accepts custom description."""
        entry = GroupEntry(
            name="test",
            calculator=lambda df, avail: {},
            order=1,
            description="Custom description",
        )

        assert entry.description == "Custom description"

    def test_dependencies_default_empty(self):
        """Dependencies default to empty list."""
        entry = GroupEntry(
            name="test",
            calculator=lambda df, avail: {},
            order=1,
        )

        assert entry.dependencies == []


class TestGroupRegistryRegister:
    """Tests for GroupRegistry.register decorator."""

    def setup_method(self):
        """Clear registry before each test."""
        GroupRegistry.clear()

    def test_register_basic(self):
        """Basic registration via decorator."""
        @GroupRegistry.register("test_group", order=1)
        def calc_test(df, available):
            return {"test_indicator": df["close"]}

        entry = GroupRegistry.get("test_group")

        assert entry is not None
        assert entry.name == "test_group"
        assert entry.order == 1
        assert callable(entry.calculator)

    def test_register_with_dependencies(self):
        """Registration with dependencies."""
        @GroupRegistry.register("child", order=2, dependencies=["parent"])
        def calc_child(df, available):
            return {}

        deps = GroupRegistry.get_dependencies("child")

        assert deps == ["parent"]

    def test_register_with_description(self):
        """Registration with custom description."""
        @GroupRegistry.register(
            "described",
            order=1,
            description="This is a described group"
        )
        def calc_described(df, available):
            return {}

        entry = GroupRegistry.get("described")

        assert entry.description == "This is a described group"

    def test_register_preserves_function(self):
        """Decorator preserves original function."""
        @GroupRegistry.register("preserved", order=1)
        def my_calculator(df, available):
            return {"result": 42}

        # Function is still callable directly
        result = my_calculator(None, set())
        assert result["result"] == 42


class TestGroupRegistryGet:
    """Tests for GroupRegistry get methods."""

    def setup_method(self):
        GroupRegistry.clear()

    def test_get_existing(self):
        """Get existing group."""
        @GroupRegistry.register("existing", order=1)
        def calc(df, available):
            return {}

        entry = GroupRegistry.get("existing")

        assert entry is not None
        assert entry.name == "existing"

    def test_get_nonexistent(self):
        """Get nonexistent group returns None."""
        assert GroupRegistry.get("nonexistent") is None

    def test_get_calculator_existing(self):
        """Get calculator for existing group."""
        @GroupRegistry.register("with_calc", order=1)
        def calc_func(df, available):
            return {"val": 123}

        calculator = GroupRegistry.get_calculator("with_calc")

        assert calculator is not None
        assert calculator(None, set())["val"] == 123

    def test_get_calculator_nonexistent(self):
        """Get calculator for nonexistent group returns None."""
        assert GroupRegistry.get_calculator("nonexistent") is None


class TestGroupRegistryOrdering:
    """Tests for group ordering."""

    def setup_method(self):
        GroupRegistry.clear()

    def test_get_ordered(self):
        """get_ordered returns groups sorted by order."""
        @GroupRegistry.register("c", order=3)
        def calc_c(df, available):
            return {}

        @GroupRegistry.register("a", order=1)
        def calc_a(df, available):
            return {}

        @GroupRegistry.register("b", order=2)
        def calc_b(df, available):
            return {}

        ordered = GroupRegistry.get_ordered()
        names = [e.name for e in ordered]

        assert names == ["a", "b", "c"]

    def test_get_ordered_items(self):
        """get_ordered_items returns list of tuples."""
        @GroupRegistry.register("x", order=2)
        def calc_x(df, available):
            return {}

        @GroupRegistry.register("y", order=1)
        def calc_y(df, available):
            return {}

        items = GroupRegistry.get_ordered_items()

        assert len(items) == 2
        assert items[0][0] == "y"  # First by order
        assert items[1][0] == "x"
        assert all(callable(item[1]) for item in items)


class TestGroupRegistryUtilities:
    """Tests for utility methods."""

    def setup_method(self):
        GroupRegistry.clear()

    def test_get_all_names(self):
        """get_all_names returns list of names."""
        @GroupRegistry.register("g1", order=1)
        def calc_g1(df, available):
            return {}

        @GroupRegistry.register("g2", order=2)
        def calc_g2(df, available):
            return {}

        names = GroupRegistry.get_all_names()

        assert "g1" in names
        assert "g2" in names

    def test_get_dependencies(self):
        """get_dependencies returns dependency list."""
        @GroupRegistry.register("with_deps", order=1, dependencies=["dep1", "dep2"])
        def calc(df, available):
            return {}

        deps = GroupRegistry.get_dependencies("with_deps")

        assert deps == ["dep1", "dep2"]

    def test_get_dependencies_nonexistent(self):
        """get_dependencies returns empty for nonexistent."""
        deps = GroupRegistry.get_dependencies("nonexistent")
        assert deps == []

    def test_get_metadata(self):
        """get_metadata returns group info."""
        @GroupRegistry.register(
            "meta_group",
            order=5,
            dependencies=["dep1", "dep2"],
            description="Test description"
        )
        def calc_meta(df, available):
            return {}

        meta = GroupRegistry.get_metadata("meta_group")

        assert meta["name"] == "meta_group"
        assert meta["order"] == 5
        assert meta["dependencies"] == ["dep1", "dep2"]
        assert meta["description"] == "Test description"

    def test_get_metadata_nonexistent(self):
        """get_metadata returns empty dict for nonexistent."""
        meta = GroupRegistry.get_metadata("nonexistent")
        assert meta == {}

    def test_get_all_metadata(self):
        """get_all_metadata returns metadata for all groups."""
        @GroupRegistry.register("g1", order=1)
        def calc_g1(df, available):
            return {}

        @GroupRegistry.register("g2", order=2)
        def calc_g2(df, available):
            return {}

        all_meta = GroupRegistry.get_all_metadata()

        assert "g1" in all_meta
        assert "g2" in all_meta
        assert all_meta["g1"]["order"] == 1
        assert all_meta["g2"]["order"] == 2

    def test_clear(self):
        """clear removes all registrations."""
        @GroupRegistry.register("temp", order=1)
        def calc_temp(df, available):
            return {}

        assert GroupRegistry.get("temp") is not None

        GroupRegistry.clear()

        assert GroupRegistry.get("temp") is None


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def setup_method(self):
        GroupRegistry.clear()

    def test_get_ordered_groups(self):
        """get_ordered_groups returns list of (name, calculator)."""
        @GroupRegistry.register("x", order=1)
        def calc_x(df, available):
            return {"x": 1}

        result = get_ordered_groups()

        assert len(result) == 1
        assert result[0][0] == "x"
        assert callable(result[0][1])
        assert result[0][1](None, set())["x"] == 1

    def test_get_group_calculator_function(self):
        """get_group_calculator is shortcut for GroupRegistry."""
        @GroupRegistry.register("y", order=1)
        def calc_y(df, available):
            return {"val": 1}

        calc = get_group_calculator("y")

        assert calc is not None
        assert calc(None, set())["val"] == 1

    def test_get_group_order(self):
        """get_group_order returns group's order."""
        @GroupRegistry.register("ordered", order=42)
        def calc(df, available):
            return {}

        order = get_group_order("ordered")

        assert order == 42

    def test_get_group_order_nonexistent(self):
        """get_group_order returns 999 for nonexistent."""
        order = get_group_order("nonexistent")
        assert order == 999
