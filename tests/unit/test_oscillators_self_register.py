"""
Этап 5 pilot: self-registering oscillators group.

Verifies that calc_oscillator_indicators registers itself via
@GroupRegistry.register while metadata stays centralized in GROUP_METADATA.
"""

import importlib
import sys

from src.features.indicator_groups.registry import GroupRegistry

# Module path used throughout tests
_OSCILLATORS_MODULE = "src.features.indicator_groups.oscillators"
_OVERLAP_MODULE = "src.features.indicator_groups.overlap"


def _reload_oscillators_fresh(registry: GroupRegistry | None = None) -> None:
    """Remove oscillators from sys.modules and re-import it.

    This forces the module-level @GroupRegistry.register decorator to fire
    again, simulating a fresh process import.
    """
    sys.modules.pop(_OSCILLATORS_MODULE, None)
    if registry is not None:
        # Use registry's clear to reset state before re-importing
        GroupRegistry.clear()
    import src.features.indicator_groups.oscillators  # noqa: F401


def _reload_overlap_fresh() -> None:
    """Remove overlap from sys.modules and re-import it."""
    sys.modules.pop(_OVERLAP_MODULE, None)
    import src.features.indicator_groups.overlap  # noqa: F401


class TestOscillatorsSelfRegistration:
    """Oscillators group registers itself via decorator on import."""

    def test_not_in_group_calculators_dict(self):
        """oscillators is absent from the legacy GROUP_CALCULATORS dict."""
        from src.features.indicator_groups import GROUP_CALCULATORS

        assert "oscillators" not in GROUP_CALCULATORS

    def test_not_in_group_metadata_dict(self):
        """oscillators metadata lives in the shared GROUP_METADATA source of truth."""
        from src.features.indicator_groups import GROUP_METADATA

        assert "oscillators" in GROUP_METADATA
        assert GROUP_METADATA["oscillators"]["dependencies"] == ["overlap", "ma"]
        assert GROUP_METADATA["oscillators"]["order"] == 2

    def test_registered_after_module_import(self):
        """After a fresh import of oscillators.py, the group is registered."""
        _reload_oscillators_fresh()

        entry = GroupRegistry.get("oscillators")
        assert entry is not None

    def test_entry_metadata(self):
        """Self-registered entry carries correct metadata."""
        _reload_oscillators_fresh()

        entry = GroupRegistry.get("oscillators")
        assert entry is not None
        assert entry.order == 2
        assert "overlap" in entry.dependencies
        assert "ma" in entry.dependencies
        assert entry.description != ""

    def test_calculator_is_the_function(self):
        """Registered calculator is the actual calc_oscillator_indicators."""
        _reload_oscillators_fresh()

        import src.features.indicator_groups.oscillators as osc_mod

        entry = GroupRegistry.get("oscillators")
        assert entry is not None
        assert entry.calculator is osc_mod.calc_oscillator_indicators

    def test_present_in_get_ordered_after_import(self):
        """After importing oscillators, get_ordered_items includes it."""
        _reload_oscillators_fresh()

        items = GroupRegistry.get_ordered_items()
        names = [name for name, _ in items]
        assert "oscillators" in names

    def test_runtime_bootstrap_restores_group_after_clear(self):
        """Public runtime path restores groups even after explicit registry clear."""
        GroupRegistry.clear()
        sys.modules.pop(_OSCILLATORS_MODULE, None)

        assert "oscillators" not in GroupRegistry._get_self_registered_groups()
        assert GroupRegistry.get("oscillators") is not None

    def test_dedup_on_reload(self):
        """Re-loading the module does not duplicate the registration."""
        _reload_oscillators_fresh()  # first load

        import src.features.indicator_groups.oscillators as osc_mod

        importlib.reload(osc_mod)  # second load

        names = GroupRegistry.get_all_names()
        assert names.count("oscillators") == 1


class TestGroupCalculatorsLegacyStillWorks:
    """Legacy groups and self-registering groups still compose correctly."""

    def test_overlap_not_in_legacy_dicts(self):
        """overlap stays self-registering but shares GROUP_METADATA."""
        from src.features.indicator_groups import GROUP_CALCULATORS, GROUP_METADATA

        assert "overlap" not in GROUP_CALCULATORS
        assert "overlap" in GROUP_METADATA
        assert GROUP_METADATA["overlap"]["dependencies"] == []
        assert GROUP_METADATA["overlap"]["order"] == 0

    def test_overlap_registered_after_module_import(self):
        """After a fresh import of overlap.py, the group is registered."""
        GroupRegistry.clear()
        _reload_overlap_fresh()

        entry = GroupRegistry.get("overlap")
        assert entry is not None
        assert entry.order == 0
        assert entry.dependencies == []

    def test_legacy_groups_loaded_on_get_ordered(self):
        """Legacy groups plus self-registering overlap are available."""
        GroupRegistry.clear()
        _reload_overlap_fresh()
        items = GroupRegistry.get_ordered_items()
        names = [name for name, _ in items]

        for expected in [
            "overlap", "ma", "volatility", "volume", "trend",
            "squeeze", "candles", "statistics", "performance",
        ]:
            assert expected in names, f"Expected '{expected}' in registry"

    def test_oscillators_included_via_combined_path(self):
        """oscillators is present after clear + fresh import + get_ordered_items.

        Sequence:
          1. clear() → empty registry, __initialized=False
          2. fresh import of oscillators → decorator fires, "oscillators" in registry
          3. get_ordered_items() → __ensure_initialized() → __import_legacy_groups()
             adds the 9 other groups (oscillators already present, skipped)
        """
        GroupRegistry.clear()
        _reload_overlap_fresh()
        _reload_oscillators_fresh()  # re-imports oscillators after clear

        items = GroupRegistry.get_ordered_items()
        names = [name for name, _ in items]

        assert "overlap" in names
        assert "oscillators" in names

    def test_all_ten_groups_present(self):
        """Total of 10 groups are available after clear + fresh import + init."""
        GroupRegistry.clear()
        _reload_overlap_fresh()
        _reload_oscillators_fresh()  # re-imports oscillators into cleared registry

        items = GroupRegistry.get_ordered_items()
        names = [name for name, _ in items]

        assert len(names) == 10
        assert set(names) == {
            "overlap", "ma", "oscillators", "volatility", "volume",
            "trend", "squeeze", "candles", "statistics", "performance",
        }
