from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.candles.domain.repair import NoProgressPolicy


def test_default_values() -> None:
    policy = NoProgressPolicy()

    assert policy.critical_timeframes == frozenset({"1H"})
    assert policy.no_progress_threshold == 3


def test_default_instances_are_equal() -> None:
    assert NoProgressPolicy() == NoProgressPolicy()


def test_is_critical_false_for_1m() -> None:
    assert NoProgressPolicy().is_critical("1m") is False


def test_is_critical_true_for_1h() -> None:
    assert NoProgressPolicy().is_critical("1H") is True


def test_is_critical_false_for_1d() -> None:
    assert NoProgressPolicy().is_critical("1D") is False


def test_is_critical_false_for_unknown() -> None:
    assert NoProgressPolicy().is_critical("5m") is False


def test_frozen_prevents_mutation() -> None:
    policy = NoProgressPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.no_progress_threshold = 10  # type: ignore[misc]


def test_custom_policy() -> None:
    policy = NoProgressPolicy(
        critical_timeframes=frozenset({"5m"}),
        no_progress_threshold=5,
    )
    assert policy.is_critical("5m") is True
    assert policy.is_critical("1m") is False
    assert policy.no_progress_threshold == 5
