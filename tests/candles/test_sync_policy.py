from src.candles.sync_policy import SwapSyncPolicy


def test_policy_retry_and_rate_limit_detection() -> None:
    policy = SwapSyncPolicy(max_retries=3, retry_delay=1.0, batch_size=300)
    assert policy.is_retriable("429 Too Many Requests")
    assert policy.is_rate_limited("50011")
    assert not policy.is_retriable("hard failure")
    assert not policy.is_rate_limited("hard failure")


def test_policy_delay_and_backoff() -> None:
    policy = SwapSyncPolicy(
        max_retries=3,
        retry_delay=0.1,
        batch_size=300,
        random_uniform=lambda _a, _b: 0.25,
    )
    assert policy.initial_delay() == 0.5
    assert policy.next_sleep(1.0) == 1.25
    assert policy.bump_delay(1.0) == 1.5


def test_policy_retry_guard_and_batch_limit() -> None:
    policy = SwapSyncPolicy(max_retries=2, retry_delay=1.0, batch_size=0)
    assert policy.request_limit() == 1
    assert policy.can_retry(0)
    assert policy.can_retry(1)
    assert not policy.can_retry(2)
