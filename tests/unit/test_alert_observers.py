"""
Unit tests for Alert Observers (Task 13).

Tests the Observer pattern for extensible alert channels.
"""

import pytest

from src.features.infrastructure.alerts import (
    AlertContext,
    AlertDispatcher,
    AlertLevel,
    AlertObserver,
    get_alert_dispatcher,
)


class TestAlertLevel:
    """Tests for AlertLevel enum."""

    def test_info_level(self):
        """INFO level exists."""
        assert AlertLevel.INFO.value == "info"

    def test_warning_level(self):
        """WARNING level exists."""
        assert AlertLevel.WARNING.value == "warning"

    def test_error_level(self):
        """ERROR level exists."""
        assert AlertLevel.ERROR.value == "error"

    def test_critical_level(self):
        """CRITICAL level exists."""
        assert AlertLevel.CRITICAL.value == "critical"


class TestAlertContext:
    """Tests for AlertContext dataclass."""

    def test_required_fields(self):
        """AlertContext requires essential fields."""
        ctx = AlertContext(
            dag_id="test_dag",
            task_id="test_task",
            execution_date="2026-02-02",
            run_id="abc123",
            try_number=1,
        )

        assert ctx.dag_id == "test_dag"
        assert ctx.task_id == "test_task"
        assert ctx.execution_date == "2026-02-02"
        assert ctx.run_id == "abc123"
        assert ctx.try_number == 1

    def test_default_level(self):
        """Default level is ERROR."""
        ctx = AlertContext(
            dag_id="dag",
            task_id="task",
            execution_date="2026-02-02",
            run_id="run",
            try_number=1,
        )

        assert ctx.level == AlertLevel.ERROR

    def test_custom_level(self):
        """Custom level can be set."""
        ctx = AlertContext(
            dag_id="dag",
            task_id="task",
            execution_date="2026-02-02",
            run_id="run",
            try_number=1,
            level=AlertLevel.WARNING,
        )

        assert ctx.level == AlertLevel.WARNING

    def test_optional_fields_default_none(self):
        """Optional fields default to None."""
        ctx = AlertContext(
            dag_id="dag",
            task_id="task",
            execution_date="2026-02-02",
            run_id="run",
            try_number=1,
        )

        assert ctx.log_url is None
        assert ctx.duration_seconds is None
        assert ctx.error_message is None

    def test_optional_fields_custom(self):
        """Optional fields can be set."""
        ctx = AlertContext(
            dag_id="dag",
            task_id="task",
            execution_date="2026-02-02",
            run_id="run",
            try_number=1,
            log_url="http://logs/123",
            duration_seconds=45.5,
            error_message="Test error",
        )

        assert ctx.log_url == "http://logs/123"
        assert ctx.duration_seconds == 45.5
        assert ctx.error_message == "Test error"

    def test_to_dict(self):
        """to_dict converts context to dictionary."""
        ctx = AlertContext(
            dag_id="test_dag",
            task_id="test_task",
            execution_date="2026-02-02",
            run_id="abc123",
            try_number=2,
            level=AlertLevel.WARNING,
        )

        d = ctx.to_dict()

        assert d["dag_id"] == "test_dag"
        assert d["task_id"] == "test_task"
        assert d["try_number"] == 2
        assert d["level"] == "warning"  # String value

    def test_to_json(self):
        """to_json converts context to JSON string."""
        ctx = AlertContext(
            dag_id="test_dag",
            task_id="test_task",
            execution_date="2026-02-02",
            run_id="abc123",
            try_number=1,
        )

        json_str = ctx.to_json()

        assert "test_dag" in json_str
        assert "test_task" in json_str
        assert "abc123" in json_str


class MockObserver(AlertObserver):
    """Mock observer for testing."""

    def __init__(self, should_succeed=True, name="MockObserver"):
        self._should_succeed = should_succeed
        self._name = name
        self.notified_contexts = []

    def notify(self, alert_ctx):
        self.notified_contexts.append(alert_ctx)
        return self._should_succeed


class FailingObserver(AlertObserver):
    """Observer that raises exception."""

    def notify(self, alert_ctx):
        raise RuntimeError("Observer failed!")


class TestAlertDispatcher:
    """Tests for AlertDispatcher (Task 13)."""

    @pytest.fixture
    def alert_ctx(self):
        """Sample alert context."""
        return AlertContext(
            dag_id="features_dag",
            task_id="calculate",
            execution_date="2026-02-02",
            run_id="run_123",
            try_number=1,
        )

    def test_subscribe(self):
        """subscribe adds observer to dispatcher."""
        dispatcher = AlertDispatcher()
        observer = MockObserver()

        dispatcher.subscribe(observer)

        assert len(dispatcher) == 1

    def test_subscribe_fluent(self):
        """subscribe returns dispatcher for fluent interface."""
        obs1 = MockObserver()
        obs2 = MockObserver()

        dispatcher = (
            AlertDispatcher()
            .subscribe(obs1)
            .subscribe(obs2)
        )

        assert len(dispatcher) == 2

    def test_subscribe_no_duplicates(self):
        """subscribe doesn't add same observer twice."""
        dispatcher = AlertDispatcher()
        observer = MockObserver()

        dispatcher.subscribe(observer)
        dispatcher.subscribe(observer)

        assert len(dispatcher) == 1

    def test_unsubscribe(self):
        """unsubscribe removes observer."""
        dispatcher = AlertDispatcher()
        observer = MockObserver()

        dispatcher.subscribe(observer)
        dispatcher.unsubscribe(observer)

        assert len(dispatcher) == 0

    def test_unsubscribe_nonexistent(self):
        """unsubscribe with nonexistent observer is safe."""
        dispatcher = AlertDispatcher()
        observer = MockObserver()

        # Should not raise
        dispatcher.unsubscribe(observer)

        assert len(dispatcher) == 0

    def test_clear(self):
        """clear removes all observers."""
        dispatcher = AlertDispatcher()
        dispatcher.subscribe(MockObserver())
        dispatcher.subscribe(MockObserver())

        dispatcher.clear()

        assert len(dispatcher) == 0

    def test_notify_all_calls_observers(self, alert_ctx):
        """notify_all calls all subscribed observers."""
        dispatcher = AlertDispatcher()
        obs1 = MockObserver()
        obs2 = MockObserver()

        dispatcher.subscribe(obs1).subscribe(obs2)
        dispatcher.notify_all(alert_ctx)

        assert len(obs1.notified_contexts) == 1
        assert len(obs2.notified_contexts) == 1
        assert obs1.notified_contexts[0] is alert_ctx
        assert obs2.notified_contexts[0] is alert_ctx

    def test_notify_all_returns_results(self, alert_ctx):
        """notify_all returns dict of observer results."""
        dispatcher = AlertDispatcher()
        obs_ok = MockObserver(should_succeed=True)
        obs_fail = MockObserver(should_succeed=False)

        dispatcher.subscribe(obs_ok).subscribe(obs_fail)
        results = dispatcher.notify_all(alert_ctx)

        # Both observers called, results recorded
        assert "MockObserver" in results

    def test_notify_all_handles_exception(self, alert_ctx):
        """notify_all handles observer exceptions gracefully."""
        dispatcher = AlertDispatcher()
        obs_ok = MockObserver()
        obs_failing = FailingObserver()

        dispatcher.subscribe(obs_ok).subscribe(obs_failing)
        results = dispatcher.notify_all(alert_ctx)

        # OK observer still called
        assert len(obs_ok.notified_contexts) == 1
        # Failing observer recorded as failed
        assert results.get("FailingObserver") is False

    def test_notify_all_empty_dispatcher(self, alert_ctx):
        """notify_all with no observers returns empty dict."""
        dispatcher = AlertDispatcher()
        results = dispatcher.notify_all(alert_ctx)

        assert results == {}

    def test_len(self):
        """len returns number of observers."""
        dispatcher = AlertDispatcher()

        assert len(dispatcher) == 0

        dispatcher.subscribe(MockObserver())
        assert len(dispatcher) == 1

        dispatcher.subscribe(MockObserver())
        assert len(dispatcher) == 2


class TestAlertDispatcherSingleton:
    """Tests for AlertDispatcher singleton access."""

    def test_get_instance_returns_singleton(self):
        """get_instance returns same instance."""
        # Reset singleton
        AlertDispatcher._instance = None

        d1 = AlertDispatcher.get_instance()
        d2 = AlertDispatcher.get_instance()

        assert d1 is d2

    def test_get_instance_creates_dispatcher(self):
        """get_instance creates AlertDispatcher."""
        AlertDispatcher._instance = None

        dispatcher = AlertDispatcher.get_instance()

        assert isinstance(dispatcher, AlertDispatcher)


class TestGetAlertDispatcher:
    """Tests for get_alert_dispatcher function."""

    def test_returns_dispatcher(self):
        """get_alert_dispatcher returns AlertDispatcher."""
        dispatcher = get_alert_dispatcher()

        assert isinstance(dispatcher, AlertDispatcher)

    def test_returns_singleton(self):
        """get_alert_dispatcher returns singleton."""
        d1 = get_alert_dispatcher()
        d2 = get_alert_dispatcher()

        assert d1 is d2


class TestAlertObserverInterface:
    """Tests for AlertObserver base class."""

    def test_notify_raises_not_implemented(self):
        """notify method raises NotImplementedError if not overridden."""
        # AlertObserver is not ABC, but notify() raises NotImplementedError
        observer = AlertObserver()
        ctx = AlertContext(
            dag_id="test",
            task_id="task",
            execution_date="2026-02-02",
            run_id="run",
            try_number=1,
        )

        with pytest.raises(NotImplementedError):
            observer.notify(ctx)

    def test_custom_observer_implementation(self):
        """Custom observer can be implemented."""
        notified = []

        class CustomObserver(AlertObserver):
            def notify(self, alert_ctx):
                notified.append(alert_ctx.dag_id)
                return True

        observer = CustomObserver()
        ctx = AlertContext(
            dag_id="custom_dag",
            task_id="task",
            execution_date="2026-02-02",
            run_id="run",
            try_number=1,
        )

        result = observer.notify(ctx)

        assert result is True
        assert "custom_dag" in notified
