"""Retry policy with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryDecision:
    should_retry: bool
    delay_seconds: float
    attempt: int


class RetryPolicy:
    def __init__(
        self,
        max_attempts: int = 4,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 60.0,
        jitter_seconds: float = 0.25,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.jitter_seconds = jitter_seconds

    def decision(self, attempt: int, retry_after_seconds: float | None = None) -> RetryDecision:
        if attempt >= self.max_attempts:
            return RetryDecision(False, 0.0, attempt)
        if retry_after_seconds is not None:
            delay = min(self.max_delay_seconds, max(0.0, retry_after_seconds))
        else:
            exponential = self.base_delay_seconds * (2 ** max(0, attempt - 1))
            jitter = random.uniform(0.0, self.jitter_seconds) if self.jitter_seconds else 0.0
            delay = min(self.max_delay_seconds, exponential + jitter)
        return RetryDecision(True, delay, attempt)

    async def run_async(
        self,
        operation: Callable[[], Awaitable[T]],
        is_retryable: Callable[[Exception], bool],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> T:
        attempt = 1
        while True:
            try:
                return await operation()
            except Exception as exc:
                if not is_retryable(exc):
                    raise
                retry_after = getattr(exc, "retry_after_seconds", None)
                decision = self.decision(attempt, retry_after_seconds=retry_after)
                if not decision.should_retry:
                    raise
                await sleep(decision.delay_seconds)
                attempt += 1
