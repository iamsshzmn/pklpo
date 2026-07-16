"""Tests for CircuitBreaker state transitions."""

from __future__ import annotations

import time

from src.candles.domain.policies import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class TestCircuitBreakerTransitions:
    def test_starts_closed(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state is CircuitState.CLOSED
        assert not cb.is_open

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state is CircuitState.CLOSED

    def test_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state is CircuitState.OPEN
        assert cb.is_open

    def test_success_resets_failure_count(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        cb.record_failure()
        assert cb.state is CircuitState.CLOSED

    def test_transitions_to_half_open_after_cooldown(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown_sec=0.1)
        cb.record_failure()
        assert cb.state is CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state is CircuitState.HALF_OPEN

    def test_half_open_success_closes(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown_sec=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state is CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state is CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, cooldown_sec=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state is CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state is CircuitState.OPEN

    def test_reset(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        assert cb.state is CircuitState.OPEN

        cb.reset()
        assert cb.state is CircuitState.CLOSED
        assert not cb.is_open


class TestCircuitOpenError:
    def test_message(self) -> None:
        err = CircuitOpenError("okx_api")
        assert "okx_api" in str(err)
        assert err.circuit_name == "okx_api"
