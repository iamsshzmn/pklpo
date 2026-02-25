"""
Unit tests for Pipeline Context (Task 11).

Tests the ISP-compliant context separation.
"""

from src.features.core.pipeline import (
    BaseContext,
    GroupCalculationContext,
    PipelineContext,
)


class TestBaseContext:
    """Tests for BaseContext dataclass."""

    def test_default_values(self):
        """BaseContext has sensible defaults."""
        ctx = BaseContext()

        assert ctx.symbol == "unknown"
        assert ctx.timeframe == "unknown"
        assert ctx.feature_count == 0
        assert len(ctx.run_id) == 12  # UUID hex[:12]

    def test_custom_values(self):
        """BaseContext accepts custom values."""
        ctx = BaseContext(
            symbol="BTC-USDT",
            timeframe="1h",
            feature_count=50,
        )

        assert ctx.symbol == "BTC-USDT"
        assert ctx.timeframe == "1h"
        assert ctx.feature_count == 50

    def test_run_id_unique(self):
        """Each context has unique run_id."""
        ctx1 = BaseContext()
        ctx2 = BaseContext()

        assert ctx1.run_id != ctx2.run_id

    def test_run_id_format(self):
        """run_id is 12 character hex string."""
        ctx = BaseContext()

        assert len(ctx.run_id) == 12
        # Should be valid hex
        int(ctx.run_id, 16)


class TestGroupCalculationContext:
    """Tests for GroupCalculationContext (Task 11)."""

    def test_inherits_base_fields(self):
        """GroupCalculationContext inherits BaseContext fields."""
        ctx = GroupCalculationContext(
            symbol="ETH-USDT",
            timeframe="5m",
            feature_count=100,
        )

        assert ctx.symbol == "ETH-USDT"
        assert ctx.timeframe == "5m"
        assert ctx.feature_count == 100
        assert len(ctx.run_id) == 12

    def test_additional_fields_defaults(self):
        """GroupCalculationContext has additional fields with defaults."""
        ctx = GroupCalculationContext()

        assert ctx.failed_groups == []
        assert ctx.data_status == "ok"

    def test_failed_groups_is_list(self):
        """failed_groups is an empty list by default."""
        ctx = GroupCalculationContext()

        assert isinstance(ctx.failed_groups, list)
        assert len(ctx.failed_groups) == 0

    def test_failed_groups_tracking(self):
        """failed_groups can track failures."""
        ctx = GroupCalculationContext()

        ctx.failed_groups.append("trend")
        ctx.failed_groups.append("volatility")

        assert "trend" in ctx.failed_groups
        assert "volatility" in ctx.failed_groups
        assert len(ctx.failed_groups) == 2

    def test_data_status_default(self):
        """data_status defaults to 'ok'."""
        ctx = GroupCalculationContext()
        assert ctx.data_status == "ok"

    def test_data_status_custom(self):
        """data_status can be customized."""
        ctx = GroupCalculationContext(data_status="warmup")
        assert ctx.data_status == "warmup"

    def test_failed_groups_isolation(self):
        """Each context has its own failed_groups list."""
        ctx1 = GroupCalculationContext()
        ctx2 = GroupCalculationContext()

        ctx1.failed_groups.append("trend")

        assert "trend" in ctx1.failed_groups
        assert "trend" not in ctx2.failed_groups


class TestPipelineContextAlias:
    """Tests for PipelineContext backward compatibility alias."""

    def test_alias_is_same_class(self):
        """PipelineContext is same as GroupCalculationContext."""
        assert PipelineContext is GroupCalculationContext

    def test_backward_compatible_usage(self):
        """PipelineContext can be used like before."""
        ctx = PipelineContext(
            symbol="BTC-USDT",
            timeframe="1m",
            feature_count=200,
        )

        assert isinstance(ctx, GroupCalculationContext)
        assert ctx.symbol == "BTC-USDT"
        assert ctx.timeframe == "1m"
        assert ctx.feature_count == 200

    def test_isinstance_check(self):
        """PipelineContext instances pass isinstance checks."""
        ctx = PipelineContext()

        assert isinstance(ctx, PipelineContext)
        assert isinstance(ctx, GroupCalculationContext)
        assert isinstance(ctx, BaseContext)


class TestContextUsagePatterns:
    """Tests for typical context usage patterns."""

    def test_context_for_logging(self):
        """Context provides info for logging."""
        ctx = GroupCalculationContext(
            symbol="BTC-USDT",
            timeframe="1h",
        )

        # Typical log message format
        log_msg = f"[{ctx.run_id}] Processing {ctx.symbol}/{ctx.timeframe}"

        assert ctx.run_id in log_msg
        assert "BTC-USDT" in log_msg
        assert "1h" in log_msg

    def test_context_error_tracking(self):
        """Context tracks errors during calculation."""
        ctx = GroupCalculationContext(
            symbol="ETH-USDT",
            timeframe="5m",
        )

        # Simulate group calculation failures
        try:
            raise ValueError("Test error in trend group")
        except ValueError:
            ctx.failed_groups.append("trend")
            ctx.data_status = "partial"

        assert "trend" in ctx.failed_groups
        assert ctx.data_status == "partial"

    def test_context_immutable_base_fields(self):
        """Base identification fields remain constant."""
        ctx = GroupCalculationContext(
            symbol="BTC-USDT",
            timeframe="1h",
        )

        original_run_id = ctx.run_id
        original_symbol = ctx.symbol

        # Modify mutable fields
        ctx.failed_groups.append("trend")
        ctx.data_status = "error"

        # Base fields unchanged
        assert ctx.run_id == original_run_id
        assert ctx.symbol == original_symbol
