from __future__ import annotations

import pytest

from ai_intel.utils.retry import RetryPolicy


def test_retry_decision_honors_retry_after() -> None:
    policy = RetryPolicy(max_attempts=4, max_delay_seconds=10)
    decision = policy.decision(attempt=1, retry_after_seconds=30)
    assert decision.should_retry is True
    assert decision.delay_seconds == 10


@pytest.mark.asyncio
async def test_run_async_retries_retryable_errors() -> None:
    attempts = 0
    sleeps: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "ok"

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0.01, jitter_seconds=0)
    result = await policy.run_async(operation, is_retryable=lambda exc: True, sleep=sleep)

    assert result == "ok"
    assert attempts == 3
    assert sleeps == [0.01, 0.02]


@pytest.mark.asyncio
async def test_run_async_uses_retry_after_from_exception() -> None:
    class RetryAfterError(RuntimeError):
        retry_after_seconds = 5.0

    attempts = 0
    sleeps: list[float] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RetryAfterError("wait")
        return "ok"

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    policy = RetryPolicy(max_attempts=2, max_delay_seconds=10, jitter_seconds=0)
    result = await policy.run_async(operation, is_retryable=lambda exc: True, sleep=sleep)

    assert result == "ok"
    assert sleeps == [5.0]
