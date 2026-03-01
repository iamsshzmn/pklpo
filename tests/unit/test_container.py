"""
Unit tests for DI Container (Task 10).

Tests the DIP-compliant dependency injection container.
"""

import pytest

from src.features.container import Container, get_container, reset_container


class TestContainerSingleton:
    """Tests for singleton registration."""

    def test_register_singleton_callable(self):
        """Singleton with callable factory is instantiated once."""
        container = Container()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"key": "value"}

        container.register_singleton("config", factory)

        result1 = container.resolve("config")
        result2 = container.resolve("config")

        assert result1 is result2  # Same object
        assert result1 == {"key": "value"}
        assert call_count == 1  # Factory called only once

    def test_register_singleton_instance(self):
        """Singleton with ready instance is returned as-is."""
        container = Container()
        instance = {"key": "value"}

        container.register_singleton("config", instance)

        assert container.resolve("config") is instance

    def test_register_instance(self):
        """register_instance is alias for singleton with instance."""
        container = Container()
        instance = {"id": 123}

        container.register_instance("my_instance", instance)

        assert container.resolve("my_instance") is instance


class TestContainerFactory:
    """Tests for factory registration."""

    def test_register_factory_new_instance_each_time(self):
        """Factory creates new instance each resolve."""
        container = Container()

        container.register_factory("service", lambda c: {"id": id(c)})

        result1 = container.resolve("service")
        result2 = container.resolve("service")

        assert result1 is not result2  # Different objects

    def test_factory_receives_container(self):
        """Factory receives container for resolving dependencies."""
        container = Container()
        container.register_singleton("config", {"db_url": "postgres://..."})
        container.register_factory("service", lambda c: {
            "config": c.resolve("config")
        })

        service = container.resolve("service")

        assert service["config"]["db_url"] == "postgres://..."

    def test_factory_can_resolve_other_factories(self):
        """Factory can resolve other factories."""
        container = Container()
        container.register_factory("dep", lambda c: {"dep_id": 1})
        container.register_factory("service", lambda c: {
            "dep": c.resolve("dep")
        })

        service = container.resolve("service")

        assert service["dep"]["dep_id"] == 1


class TestContainerResolve:
    """Tests for resolve functionality."""

    def test_resolve_not_registered(self):
        """KeyError when resolving unregistered dependency."""
        container = Container()

        with pytest.raises(KeyError, match="not registered"):
            container.resolve("unknown")

    def test_resolve_singleton_before_factory(self):
        """Singleton takes precedence over factory of same name."""
        container = Container()
        container.register_singleton("config", {"from": "singleton"})

        # This should not override
        container.register_factory("config", lambda c: {"from": "factory"})

        result = container.resolve("config")
        # Factory is registered, so it will be used (last registration wins)
        # Actually, they are stored separately, singleton is checked first
        assert result["from"] == "singleton"


class TestContainerUtilities:
    """Tests for utility methods."""

    def test_has_method(self):
        """has() returns True for registered dependencies."""
        container = Container()
        container.register_singleton("config", {})

        assert container.has("config") is True
        assert container.has("unknown") is False

    def test_contains_operator(self):
        """__contains__ supports 'in' operator."""
        container = Container()
        container.register_singleton("config", {})

        assert "config" in container
        assert "unknown" not in container

    def test_clear_method(self):
        """clear() removes all registrations."""
        container = Container()
        container.register_singleton("a", 1)
        container.register_factory("b", lambda c: 2)

        container.clear()

        assert not container.has("a")
        assert not container.has("b")

    def test_chaining(self):
        """Fluent interface for chained registration."""
        container = (
            Container()
            .register_singleton("a", 1)
            .register_factory("b", lambda c: 2)
            .register_instance("c", 3)
        )

        assert container.resolve("a") == 1
        assert container.resolve("b") == 2
        assert container.resolve("c") == 3


class TestGlobalContainer:
    """Tests for global container functions."""

    def test_get_container_singleton(self):
        """get_container returns singleton instance."""
        reset_container()

        c1 = get_container()
        c2 = get_container()

        assert c1 is c2

    def test_reset_container(self):
        """reset_container creates fresh instance."""
        c1 = get_container()
        c1.register_singleton("test", "value")

        reset_container()
        c2 = get_container()

        assert c1 is not c2
        # Note: new container has default dependencies configured

    def test_default_dependencies_configured(self):
        """Default dependencies are configured on creation."""
        reset_container()
        container = get_container()

        assert container.has("logger")
        assert container.has("calculator")
        assert container.has("validation_chain")
        assert container.has("alert_dispatcher")

    def test_resolve_logger(self):
        """Logger can be resolved from default container."""
        reset_container()
        container = get_container()

        logger = container.resolve("logger")
        assert logger is not None

    def test_resolve_calculator(self):
        """Calculator can be resolved from default container."""
        reset_container()
        container = get_container()

        calculator = container.resolve("calculator")

        from src.features.application.feature_service import FeatureCalculationService
        assert isinstance(calculator, FeatureCalculationService)

    def test_resolve_validation_chain(self):
        """Validation chain can be resolved (factory creates new each time)."""
        reset_container()
        container = get_container()

        chain1 = container.resolve("validation_chain")
        chain2 = container.resolve("validation_chain")

        # Factory registration - new instance each time
        assert chain1 is not chain2

        from src.features.validation.chain import ValidationChain
        assert isinstance(chain1, ValidationChain)

    def test_resolve_alert_dispatcher(self):
        """Alert dispatcher can be resolved."""
        reset_container()
        container = get_container()

        dispatcher = container.resolve("alert_dispatcher")

        from src.features.infrastructure.alerts import AlertDispatcher
        assert isinstance(dispatcher, AlertDispatcher)
