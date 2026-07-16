"""Tests for retry_io universal wrapper."""

from __future__ import annotations

import pytest

from src.candles.domain.policies import (
    CircuitBreaker,
    CircuitOpenError,
    RetryIOPolicy,
    retry_io,
)


class _Counter:
    def __init__(self, fail_count: int = 0, error: type[Exception] = RuntimeError):
        self.calls = 0
        self._fail_count = fail_count
        self._error = error

    async def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self._fail_count:
            raise self._error(f"fail #{self.calls}")
        return "ok"


@pytest.mark.asyncio
async def test_succeeds_on_first_try(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.domain.policies.asyncio.sleep", _no_sleep)
    fn = _Counter(fail_count=0)
    result = await retry_io(fn, policy=RetryIOPolicy(max_retries=3))
    assert result == "ok"
    assert fn.calls == 1


@pytest.mark.asyncio
async def test_retries_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.domain.policies.asyncio.sleep", _no_sleep)
    fn = _Counter(fail_count=2)
    result = await retry_io(fn, policy=RetryIOPolicy(max_retries=3))
    assert result == "ok"
    assert fn.calls == 3  # 2 fails + 1 success


@pytest.mark.asyncio
async def test_raises_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.domain.policies.asyncio.sleep", _no_sleep)
    fn = _Counter(fail_count=99)
    with pytest.raises(RuntimeError, match="fail #4"):
        await retry_io(fn, policy=RetryIOPolicy(max_retries=3))
    assert fn.calls == 4  # 1 initial + 3 retries


@pytest.mark.asyncio
async def test_non_retriable_exception_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.domain.policies.asyncio.sleep", _no_sleep)
    fn = _Counter(fail_count=1, error=ValueError)
    policy = RetryIOPolicy(max_retries=3, retriable_exceptions=(RuntimeError,))
    with pytest.raises(ValueError):
        await retry_io(fn, policy=policy)
    assert fn.calls == 1  # no retry


@pytest.mark.asyncio
async def test_circuit_breaker_rejects_when_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.domain.policies.asyncio.sleep", _no_sleep)
    cb = CircuitBreaker(name="test", failure_threshold=1)
    cb.record_failure()  # opens circuit

    fn = _Counter(fail_count=0)
    with pytest.raises(CircuitOpenError):
        await retry_io(fn, policy=RetryIOPolicy(), circuit_breaker=cb)
    assert fn.calls == 0  # never called


@pytest.mark.asyncio
async def test_circuit_breaker_records_on_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _no_sleep(_):
        return None

    monkeypatch.setattr("src.candles.domain.policies.asyncio.sleep", _no_sleep)
    cb = CircuitBreaker(name="test", failure_threshold=5)
    fn = _Counter(fail_count=2)

    result = await retry_io(fn, policy=RetryIOPolicy(max_retries=3), circuit_breaker=cb)
    assert result == "ok"
    assert cb._consecutive_failures == 0  # reset on success
