"""
Tests for retry decorators.
"""

import time

import pytest

from ..infrastructure.retry import (
    TENACITY_AVAILABLE,
    api_retry,
    database_retry,
    simple_retry,
)


class TestSimpleRetry:
    """Tests for simple_retry decorator."""

    def test_success_on_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = 0

        @simple_retry(max_attempts=3, backoff_factor=0.1)
        def always_succeeds():
            nonlocal call_count
            call_count += 1
            return "success"

        result = always_succeeds()

        assert result == "success"
        assert call_count == 1

    def test_success_after_retries(self):
        """Test function succeeds after a few retries."""
        call_count = 0

        @simple_retry(max_attempts=5, backoff_factor=0.1)
        def succeeds_on_third():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = succeeds_on_third()

        assert result == "success"
        assert call_count == 3

    def test_failure_after_max_attempts(self):
        """Test function fails after max attempts."""
        call_count = 0

        @simple_retry(max_attempts=3, backoff_factor=0.1)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_fails()

        assert call_count == 3

    def test_specific_exceptions_only(self):
        """Test retry only catches specified exceptions."""
        call_count = 0

        @simple_retry(max_attempts=3, backoff_factor=0.1, exceptions=(ValueError,))
        def raises_wrong_exception():
            nonlocal call_count
            call_count += 1
            raise TypeError("Wrong exception")

        # Should not retry TypeError
        with pytest.raises(TypeError, match="Wrong exception"):
            raises_wrong_exception()

        assert call_count == 1

    def test_backoff_timing(self):
        """Test exponential backoff is applied."""
        call_times = []

        @simple_retry(max_attempts=3, backoff_factor=0.5)
        def track_timing():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Retry")
            return "success"

        result = track_timing()

        assert result == "success"
        assert len(call_times) == 3

        # Check backoff times (approximately)
        # First retry: 0.5^0 = 0.5s
        # Second retry: 0.5^1 = 0.5s
        if len(call_times) >= 2:
            time_diff_1 = call_times[1] - call_times[0]
            assert time_diff_1 >= 0.4  # Allow some timing tolerance


class TestDatabaseRetry:
    """Tests for database_retry decorator."""

    def test_retries_connection_error(self):
        """Test database retry catches ConnectionError."""
        call_count = 0

        @database_retry(max_attempts=3, wait_multiplier=0, wait_max=0)
        def db_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("DB connection lost")
            return "success"

        result = db_operation()

        assert result == "success"
        assert call_count == 2

    def test_retries_timeout_error(self):
        """Test database retry catches TimeoutError."""
        call_count = 0

        @database_retry(max_attempts=3, wait_multiplier=0, wait_max=0)
        def db_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("DB timeout")
            return "success"

        result = db_operation()

        assert result == "success"
        assert call_count == 2


class TestApiRetry:
    """Tests for api_retry decorator."""

    def test_retries_api_errors(self):
        """Test API retry catches connection errors."""
        call_count = 0

        @api_retry(max_attempts=3, wait_multiplier=0, wait_max=0)
        def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("API unreachable")
            return {"status": "ok"}

        result = api_call()

        assert result == {"status": "ok"}
        assert call_count == 2


@pytest.mark.skipif(not TENACITY_AVAILABLE, reason="tenacity not installed")
class TestTenacityIntegration:
    """Tests for tenacity integration when available."""

    def test_tenacity_used_when_available(self):
        """Test that tenacity is used when available."""
        # This test just ensures no errors occur when tenacity is used
        call_count = 0

        @database_retry(max_attempts=2, wait_multiplier=0, wait_max=0)
        def db_op():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("DB error")
            return "success"

        result = db_op()

        assert result == "success"
        assert call_count == 2
