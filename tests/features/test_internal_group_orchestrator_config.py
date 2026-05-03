from src.features.core.group_orchestrator import GroupCalculationConfig
from src.features.indicator_groups.registry import build_registry_snapshot


def test_default_calculation_order_matches_registry_snapshot():
    config = GroupCalculationConfig()
    snapshot_order = [entry.name for entry in build_registry_snapshot().get_ordered()]

    assert config.calculation_order == snapshot_order


def test_default_config_uses_registry_as_order_source_of_truth():
    config = GroupCalculationConfig()
    snapshot_order = [entry.name for entry in build_registry_snapshot().get_ordered()]

    assert config.calculation_order == snapshot_order
