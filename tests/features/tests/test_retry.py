"""Tests for shared retry decorators in src.utils.retry."""

import time

import pytest

from src.utils import retry as retry_module
from src.utils.retry import RetryConfig, api_retry, database_retry, retry_sync


class TestRetrySync:
    """Tests for retry_sync decorator."""

    def test_success_on_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = 0

        @retry_sync(max_attempts=3, base_delay=0.1, max_delay=0.1, jitter=False)
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

        @retry_sync(max_attempts=5, base_delay=0.1, max_delay=0.1, jitter=False)
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

        @retry_sync(max_attempts=3, base_delay=0.1, max_delay=0.1, jitter=False)
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

        @retry_sync(
            max_attempts=3,
            base_delay=0.1,
            max_delay=0.1,
            jitter=False,
            exceptions=(ValueError,),
        )
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

        @retry_sync(max_attempts=3, base_delay=0.5, max_delay=0.5, jitter=False)
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
    """Tests for async database_retry decorator."""

    @pytest.mark.asyncio
    async def test_retries_connection_error(self, monkeypatch):
        """Test database retry catches ConnectionError."""
        call_count = 0
        monkeypatch.setattr(
            retry_module.RetryConfig,
            "from_settings",
            classmethod(
                lambda cls, settings=None, preset="default": RetryConfig(
                    max_attempts=3,
                    base_delay=0.0,
                    max_delay=0.0,
                    jitter=False,
                    exceptions=Exception,
                )
            ),
        )

        @database_retry(
            exceptions=(ConnectionError,),
            on_retry=lambda attempt, err, delay: None,
        )
        async def db_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("DB connection lost")
            return "success"

        result = await db_operation()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retries_timeout_error(self, monkeypatch):
        """Test database retry catches TimeoutError."""
        call_count = 0
        monkeypatch.setattr(
            retry_module.RetryConfig,
            "from_settings",
            classmethod(
                lambda cls, settings=None, preset="default": RetryConfig(
                    max_attempts=3,
                    base_delay=0.0,
                    max_delay=0.0,
                    jitter=False,
                    exceptions=Exception,
                )
            ),
        )

        @database_retry(
            exceptions=(TimeoutError,),
            on_retry=lambda attempt, err, delay: None,
        )
        async def db_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("DB timeout")
            return "success"

        result = await db_operation()

        assert result == "success"
        assert call_count == 2


class TestApiRetry:
    """Tests for async api_retry decorator."""

    @pytest.mark.asyncio
    async def test_retries_api_errors(self, monkeypatch):
        """Test API retry catches connection errors."""
        call_count = 0
        monkeypatch.setattr(
            retry_module.RetryConfig,
            "from_settings",
            classmethod(
                lambda cls, settings=None, preset="default": RetryConfig(
                    max_attempts=3,
                    base_delay=0.0,
                    max_delay=0.0,
                    jitter=False,
                    exceptions=Exception,
                )
            ),
        )

        @api_retry(
            exceptions=(ConnectionError,),
            on_retry=lambda attempt, err, delay: None,
        )
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("API unreachable")
            return {"status": "ok"}

        result = await api_call()

        assert result == {"status": "ok"}
        assert call_count == 2
