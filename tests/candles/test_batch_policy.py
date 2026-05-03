"""Unit tests for DynamicBatchPolicy."""

import pytest

from src.candles.domain.batch_policy import DynamicBatchPolicy


class TestDynamicBatchPolicy:
    def test_default_batch_size_returned_when_no_pressure(self):
        policy = DynamicBatchPolicy(default_batch_size=300)
        result = policy.get_batch_size("1m", api_latency_ms=0.0, cpu_pct=0.0)
        assert result == 300

    def test_scale_down_on_high_latency(self):
        policy = DynamicBatchPolicy(
            default_batch_size=300,
            latency_threshold_ms=500.0,
            scale_down_factor=0.8,
        )
        result = policy.get_batch_size("1m", api_latency_ms=600.0, cpu_pct=0.0)
        assert result < 300
        assert result >= policy._min

    def test_min_batch_size_on_high_cpu(self):
        policy = DynamicBatchPolicy(
            default_batch_size=300,
            min_batch_size=50,
            cpu_threshold_pct=80.0,
        )
        result = policy.get_batch_size("1m", api_latency_ms=0.0, cpu_pct=85.0)
        assert result == 50

    def test_recovery_toward_default(self):
        policy = DynamicBatchPolicy(
            default_batch_size=300,
            min_batch_size=50,
            cpu_threshold_pct=80.0,
            recovery_factor=1.1,
        )
        # First: force down to minimum via high CPU
        policy.get_batch_size("1m", api_latency_ms=0.0, cpu_pct=90.0)
        assert policy.current_batch_size == 50

        # Then: recover with no pressure
        for _ in range(30):
            policy.get_batch_size("1m", api_latency_ms=0.0, cpu_pct=0.0)

        assert policy.current_batch_size == 300

    def test_never_below_min_batch_size(self):
        policy = DynamicBatchPolicy(default_batch_size=300, min_batch_size=50)
        for _ in range(100):
            result = policy.get_batch_size("1m", api_latency_ms=9999.0, cpu_pct=99.0)
            assert result >= 50

    def test_never_above_default_batch_size(self):
        policy = DynamicBatchPolicy(default_batch_size=300)
        for _ in range(20):
            result = policy.get_batch_size("1m", api_latency_ms=0.0, cpu_pct=0.0)
            assert result <= 300

    def test_reset_restores_default(self):
        policy = DynamicBatchPolicy(default_batch_size=300)
        policy.get_batch_size("1m", api_latency_ms=0.0, cpu_pct=90.0)
        policy.reset()
        assert policy.current_batch_size == 300

    def test_exact_threshold_boundary_latency(self):
        """Latency exactly at threshold should trigger scale-down."""
        policy = DynamicBatchPolicy(
            default_batch_size=300,
            latency_threshold_ms=500.0,
            scale_down_factor=0.8,
        )
        result = policy.get_batch_size("1m", api_latency_ms=500.0, cpu_pct=0.0)
        assert result < 300

    def test_just_below_threshold_does_not_scale_down(self):
        policy = DynamicBatchPolicy(
            default_batch_size=300,
            latency_threshold_ms=500.0,
        )
        result = policy.get_batch_size("1m", api_latency_ms=499.9, cpu_pct=0.0)
        # Recovery factor pushes it up (or keeps at default), should not go below default
        assert result >= 300

    def test_tf_parameter_accepted_without_error(self):
        policy = DynamicBatchPolicy(default_batch_size=100)
        for tf in ["1m", "5m", "15m", "1H", "1D"]:
            result = policy.get_batch_size(tf, api_latency_ms=0.0, cpu_pct=0.0)
            assert isinstance(result, int)
