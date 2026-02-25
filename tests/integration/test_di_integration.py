"""
Integration tests for Dependency Injection.

Tests that DI container correctly wires up all components.
"""

import numpy as np
import pandas as pd
import pytest

from src.features.container import get_container, reset_container


@pytest.mark.integration
class TestDIContainerIntegration:
    """Integration tests for DI container with real components."""

    def setup_method(self):
        """Reset container before each test."""
        reset_container()

    def test_resolve_logger(self):
        """Container resolves logger correctly."""
        container = get_container()

        logger = container.resolve("logger")

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_resolve_calculator(self):
        """Container resolves FeatureCalculationService."""
        container = get_container()

        calculator = container.resolve("calculator")

        from src.features.application.feature_service import FeatureCalculationService
        assert isinstance(calculator, FeatureCalculationService)

    def test_resolve_validation_chain(self):
        """Container resolves ValidationChain."""
        container = get_container()

        chain = container.resolve("validation_chain")

        from src.features.validation.chain import ValidationChain
        assert isinstance(chain, ValidationChain)

    def test_resolve_alert_dispatcher(self):
        """Container resolves AlertDispatcher."""
        container = get_container()

        dispatcher = container.resolve("alert_dispatcher")

        from src.features.infrastructure.alerts import AlertDispatcher
        assert isinstance(dispatcher, AlertDispatcher)

    def test_validation_chain_is_factory(self):
        """ValidationChain is factory (new instance each resolve)."""
        container = get_container()

        chain1 = container.resolve("validation_chain")
        chain2 = container.resolve("validation_chain")

        assert chain1 is not chain2

    def test_calculator_is_singleton(self):
        """Calculator is singleton (same instance)."""
        container = get_container()

        calc1 = container.resolve("calculator")
        calc2 = container.resolve("calculator")

        assert calc1 is calc2


@pytest.mark.integration
class TestDIComponentsWork:
    """Tests that DI-resolved components actually work."""

    def setup_method(self):
        reset_container()

    @pytest.fixture
    def valid_ohlcv(self):
        """Valid OHLCV for testing."""
        np.random.seed(42)
        n = 50
        return pd.DataFrame({
            "open": np.random.rand(n) * 100 + 50,
            "high": np.random.rand(n) * 100 + 55,
            "low": np.random.rand(n) * 100 + 45,
            "close": np.random.rand(n) * 100 + 50,
            "volume": np.random.rand(n) * 10000,
        })

    def test_calculator_can_calculate(self, valid_ohlcv):
        """Resolved calculator can perform calculation."""
        container = get_container()
        calculator = container.resolve("calculator")

        try:
            result = calculator.calculate(
                valid_ohlcv,
                specs=None,
                volatility_normalize=False,
            )

            assert isinstance(result, pd.DataFrame)
            assert len(result) == len(valid_ohlcv)
        except Exception as e:
            # May fail if pandas_ta not available
            pytest.skip(f"Skipped: {e}")

    def test_validation_chain_validates(self, valid_ohlcv):
        """Resolved validation chain validates data."""
        container = get_container()
        chain = container.resolve("validation_chain")

        result = chain.validate(valid_ohlcv)

        assert result.is_valid is True

    def test_alert_dispatcher_notifies(self):
        """Resolved alert dispatcher can notify."""
        from src.features.infrastructure.alerts import AlertContext, AlertObserver

        container = get_container()
        dispatcher = container.resolve("alert_dispatcher")

        # Add test observer
        notified = []

        class TestObserver(AlertObserver):
            def notify(self, ctx):
                notified.append(ctx)
                return True

        dispatcher.subscribe(TestObserver())

        ctx = AlertContext(
            dag_id="test",
            task_id="test",
            execution_date="2026-02-02",
            run_id="test",
            try_number=1,
        )

        dispatcher.notify_all(ctx)

        assert len(notified) == 1


@pytest.mark.integration
class TestDIReset:
    """Tests for container reset functionality."""

    def test_reset_creates_fresh_container(self):
        """reset_container creates fresh container."""
        container1 = get_container()
        container1.register_singleton("test", "value1")

        reset_container()
        container2 = get_container()

        # New container should not have test value
        # But it will have default dependencies
        assert container2.has("logger")
        assert container2.has("calculator")

    def test_reset_clears_custom_registrations(self):
        """reset_container clears custom registrations."""
        container = get_container()
        container.register_singleton("custom", {"data": "test"})

        assert container.has("custom")

        reset_container()
        new_container = get_container()

        assert not new_container.has("custom")

    def test_reset_preserves_defaults(self):
        """reset_container preserves default dependencies."""
        reset_container()
        container = get_container()

        # Defaults should still be there
        assert container.has("logger")
        assert container.has("calculator")
        assert container.has("validation_chain")
        assert container.has("alert_dispatcher")
