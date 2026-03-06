"""
Simple Dependency Injection Container.

Task 10: DIP-compliant dependency management without external libraries.

This module provides a lightweight DI container for managing dependencies
in the features module. It supports:
- Singleton registration
- Factory registration
- Lazy initialization
- Type-safe resolution

Usage:
    from src.features.container import Container, create_default_container

    # Register dependencies
    container = create_default_container()
    container.register_singleton("logger", get_features_logger)
    container.register_factory("calculator", FeatureCalculationService)

    # Resolve dependencies
    logger = container.resolve("logger")
    calculator = container.resolve("calculator")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from src.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

T = TypeVar("T")


class Container:
    """
    Simple Dependency Injection Container.

    Supports singleton and factory registrations with lazy initialization.

    Example:
        container = Container()
        container.register_singleton("config", lambda: FeaturesSettings())
        container.register_factory("service", lambda c: MyService(c.resolve("config")))

        service = container.resolve("service")
    """

    def __init__(self) -> None:
        self._singletons: dict[str, Any] = {}
        self._factories: dict[str, Callable[[Container], Any]] = {}
        self._singleton_factories: dict[str, Callable[[], Any]] = {}

    def register_singleton(
        self,
        name: str,
        factory: Callable[[], T] | T,
    ) -> Container:
        """
        Register a singleton dependency.

        Args:
            name: Dependency name
            factory: Factory function or instance

        Returns:
            Self for chaining
        """
        if callable(factory):
            self._singleton_factories[name] = factory
        else:
            self._singletons[name] = factory
        return self

    def register_factory(
        self,
        name: str,
        factory: Callable[[Container], T],
    ) -> Container:
        """
        Register a factory dependency (new instance each time).

        Args:
            name: Dependency name
            factory: Factory function that receives container

        Returns:
            Self for chaining
        """
        self._factories[name] = factory
        return self

    def register_instance(self, name: str, instance: Any) -> Container:
        """
        Register an existing instance as singleton.

        Args:
            name: Dependency name
            instance: Instance to register

        Returns:
            Self for chaining
        """
        self._singletons[name] = instance
        return self

    def resolve(self, name: str) -> Any:
        """
        Resolve a dependency by name.

        Args:
            name: Dependency name

        Returns:
            Resolved dependency

        Raises:
            KeyError: If dependency not found
        """
        # Check if already instantiated singleton
        if name in self._singletons:
            return self._singletons[name]

        # Check if lazy singleton
        if name in self._singleton_factories:
            instance = self._singleton_factories[name]()
            self._singletons[name] = instance
            del self._singleton_factories[name]
            logger.debug(f"Container: Instantiated singleton '{name}'")
            return instance

        # Check if factory
        if name in self._factories:
            instance = self._factories[name](self)
            logger.debug(f"Container: Created instance from factory '{name}'")
            return instance

        raise KeyError(f"Dependency '{name}' not registered")

    def has(self, name: str) -> bool:
        """Check if dependency is registered."""
        return (
            name in self._singletons
            or name in self._singleton_factories
            or name in self._factories
        )

    def clear(self) -> Container:
        """Clear all registrations."""
        self._singletons.clear()
        self._factories.clear()
        self._singleton_factories.clear()
        return self

    def __contains__(self, name: str) -> bool:
        return self.has(name)


def create_default_container() -> Container:
    """Create a freshly configured container with default dependencies."""
    container = Container()
    _configure_default_dependencies(container)
    return container


def _configure_default_dependencies(container: Container) -> None:
    """Configure default dependencies."""
    # Logger
    from src.logging import get_features_logger

    container.register_singleton("logger", lambda: get_features_logger("features"))

    # Feature calculator service
    from .application.feature_service import FeatureCalculationService

    container.register_singleton("calculator", FeatureCalculationService)

    # Validation chain
    from .validation.chain import create_default_chain

    container.register_factory("validation_chain", lambda c: create_default_chain())

    # Alert dispatcher
    from .infrastructure.alerts import get_alert_dispatcher

    container.register_singleton("alert_dispatcher", get_alert_dispatcher)

    logger.debug("Container: Default dependencies configured")
