from __future__ import annotations

from src.features.core.group_orchestrator import GroupCalculationConfig


def test_group_calculation_config_from_settings_maps_expected_values() -> None:
    config = GroupCalculationConfig(
        calculation_order=["overlap", "ma"],
        min_rows=42,
        min_fill_rate=0.75,
        max_nan_ratio=0.2,
        feature_periods={"ema_8": 8, "sma_20": 20},
    )

    assert config.calculation_order == ["overlap", "ma"]
    assert config.min_rows == 42
    assert config.min_fill_rate == 0.75
    assert config.max_nan_ratio == 0.2
    assert config.feature_periods == {"ema_8": 8, "sma_20": 20}
