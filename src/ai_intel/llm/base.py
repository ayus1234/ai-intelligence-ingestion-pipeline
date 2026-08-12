"""Provider abstraction for LLM extraction."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RetryMetrics:
    provider: str
    attempts: int = 1
    total_wait_time: float = 0.0
    retry_after_used: bool = False
    fallback_triggered: bool = False


@dataclass(frozen=True, slots=True)
class LLMProviderResult:
    provider_name: str
    model: str
    payload: dict[str, Any]
    confidence_score: float = 1.0
    chunk_count: int = 1
    retries: int = 0
    cache_hit: bool = False
    validation_status: str = "STRICT_SUCCESS"
    retry_metrics: RetryMetrics | None = None


class LLMError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


class LLMProvider(ABC):
    name: str
    model: str
    tier: int = 1
    concurrency_limit: int = 10

    def __init__(self) -> None:
        self.semaphore = asyncio.Semaphore(self.concurrency_limit)

    @abstractmethod
    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        raise NotImplementedError
