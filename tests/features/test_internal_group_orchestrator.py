from __future__ import annotations

from src.features.core.group_orchestrator import GroupCalculationConfig


def test_group_calculation_config_from_settings_maps_expected_values() -> None:
    config = GroupCalculationConfig(
        batch_size=123,
        max_retries=7,
        min_rows=42,
        min_fill_rate=0.75,
        feature_periods={"ema_8": 8, "sma_20": 20},
    )

    assert config.batch_size == 123
    assert config.max_retries == 7
    assert config.min_rows == 42
    assert config.min_fill_rate == 0.75
    assert config.feature_periods == {"ema_8": 8, "sma_20": 20}
