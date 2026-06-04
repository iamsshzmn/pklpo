from __future__ import annotations

import pytest

from src.candles.domain.eligibility import (
    CoverageFacts,
    EligibilityState,
    TimeframeRole,
    build_timeframe_policies,
    evaluate_feature_eligibility,
)


@pytest.mark.parametrize(
    ("overrides", "expected_state"),
    [
        ({"disabled": True, "timeframe": "1M", "integrity_ok": False}, "disabled"),
        ({"timeframe": "1M", "integrity_ok": False}, "informational_only"),
        ({"integrity_ok": False, "actual_bars": 500}, "invalid_history"),
        ({"actual_bars": 499}, "insufficient_history"),
        ({"actual_bars": 500, "coverage_pct": 90.0}, "incomplete_history"),
        ({"actual_bars": 500, "has_interior_gap": True}, "incomplete_history"),
        ({"actual_bars": 500, "coverage_pct": 100.0}, "eligible"),
    ],
)
def test_eligibility_state_precedence(
    overrides: dict[str, object],
    expected_state: str,
) -> None:
    data = {
        "symbol": "BTC-USDT-SWAP",
        "timeframe": "1H",
        "actual_bars": 500,
        "coverage_pct": 100.0,
        "has_interior_gap": False,
        "integrity_ok": True,
        "disabled": False,
    }
    data.update(overrides)

    result = evaluate_feature_eligibility(CoverageFacts(**data))

    assert result.state is EligibilityState(expected_state)


def test_capability_matrix_full_research_timeframe() -> None:
    result = evaluate_feature_eligibility(
        CoverageFacts(
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            actual_bars=500,
            coverage_pct=100.0,
        )
    )

    assert result.can_compute_features
    assert result.can_score
    assert result.can_train_ml
    assert not result.context_only


def test_capability_matrix_weekly_context_timeframe() -> None:
    result = evaluate_feature_eligibility(
        CoverageFacts(
            symbol="BTC-USDT-SWAP",
            timeframe="1W",
            actual_bars=280,
            coverage_pct=100.0,
        )
    )

    assert result.can_compute_features
    assert not result.can_score
    assert not result.can_train_ml
    assert result.context_only


def test_capability_matrix_monthly_informational_timeframe() -> None:
    result = evaluate_feature_eligibility(
        CoverageFacts(
            symbol="BTC-USDT-SWAP",
            timeframe="1M",
            actual_bars=77,
            coverage_pct=100.0,
        )
    )

    assert not result.can_compute_features
    assert not result.can_score
    assert not result.can_train_ml
    assert not result.context_only


@pytest.mark.parametrize(
    ("timeframe", "bars", "eligible"),
    [
        ("1H", 499, False),
        ("4H", 499, False),
        ("1D", 499, False),
        ("1W", 279, False),
        ("1W", 280, True),
        ("1M", 10, False),
    ],
)
def test_timeframe_required_bar_boundaries(
    timeframe: str,
    bars: int,
    eligible: bool,
) -> None:
    result = evaluate_feature_eligibility(
        CoverageFacts(
            symbol="BTC-USDT-SWAP",
            timeframe=timeframe,
            actual_bars=bars,
            coverage_pct=100.0,
        )
    )

    assert (result.state is EligibilityState.ELIGIBLE) is eligible


def test_build_timeframe_policies_uses_settings_shaped_warmup_contract() -> None:
    policies = build_timeframe_policies(
        {
            "1H": 300,
            "4H": 400,
            "1D": 500,
            "1W": 120,
            "1M": 0,
        }
    )

    assert policies["1H"].required_bars == 300
    assert policies["1H"].role is TimeframeRole.FULL
    assert policies["1W"].required_bars == 120
    assert policies["1W"].role is TimeframeRole.CONTEXT
    assert policies["1M"].required_bars == 0
    assert policies["1M"].role is TimeframeRole.INFORMATIONAL


def test_custom_policy_changes_required_bar_boundary() -> None:
    policies = build_timeframe_policies({"1H": 3})

    result = evaluate_feature_eligibility(
        CoverageFacts(
            symbol="BTC-USDT-SWAP",
            timeframe="1H",
            actual_bars=3,
            coverage_pct=100.0,
        ),
        policies=policies,
    )

    assert result.state is EligibilityState.ELIGIBLE
    assert result.required_bars == 3
