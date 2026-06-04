from __future__ import annotations


def test_warmup_contract_derives_raw_requirement_from_feature_specs() -> None:
    from src.features.domain.warmup_contract import build_warmup_contract

    contract = build_warmup_contract()

    assert contract.raw_min_bars >= 233
    assert contract.feature_requirements["ema_233"] == 233
    assert contract.operational_min_bars == 280
    assert contract.recommended_bars == 500


def test_warmup_contract_covers_every_feature_spec_name() -> None:
    from src.features.domain.warmup_contract import build_warmup_contract
    from src.features.specs import FEATURE_SPECS

    contract = build_warmup_contract()

    assert set(contract.feature_requirements) == set(FEATURE_SPECS)
    assert not contract.unclassified_features


def test_warmup_contract_flags_cumulative_and_lookahead_features() -> None:
    from src.features.domain.warmup_contract import build_warmup_contract

    contract = build_warmup_contract()

    assert "obv" in contract.cumulative_features
    assert "vwap" in contract.cumulative_features
    assert isinstance(contract.lookahead_features, frozenset)


def test_features_settings_exposes_warmup_contract_defaults() -> None:
    from src.config.settings import FeaturesSettings

    settings = FeaturesSettings(_env_file=None)

    assert settings.operational_warmup_bars == 280
    assert settings.recommended_warmup_bars == 500
    assert settings.warmup_bars_by_timeframe["1H"] == 500
    assert settings.warmup_bars_by_timeframe["1W"] == 280
    assert settings.warmup_bars_by_timeframe["1M"] == 0


def test_legacy_strategy_lookback_uses_warmup_contract_for_ema_233() -> None:
    from src.features.domain.strategy import (
        get_max_lookback_for_strategies,
        max_lookback,
    )

    assert max_lookback("ema_233") == 233
    assert get_max_lookback_for_strategies(["ema_200", "ema_233"]) == 233
