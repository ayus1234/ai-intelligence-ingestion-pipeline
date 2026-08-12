"""Tests for LLM 429 retry with jitter/Retry-After and 413 chunk replay protection."""

import pytest

from ai_intel.llm import LLMError, LLMOrchestrator, LLMProvider, LLMProviderResult
from ai_intel.llm.base import RetryMetrics


class MockFlakyProvider(LLMProvider):
    name = "flaky"
    model = "flaky-v1"
    tier = 1

    def __init__(self) -> None:
        super().__init__()
        self.chunk_attempts: dict[str, int] = {}

    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        self.chunk_attempts[text] = self.chunk_attempts.get(text, 0) + 1

        # Simulate 429 rate limit with Retry-After on 1st call for chunk 1
        if "Chunk 1" in text and self.chunk_attempts[text] == 1:
            raise LLMError("Rate limit", status_code=429, retryable=True, retry_after_seconds=0.01)

        # Simulate 413 error on 1st call for chunk 2
        if "Chunk 2" in text and self.chunk_attempts[text] == 1:
            raise LLMError("Payload too large", status_code=413, retryable=True)

        return LLMProviderResult(
            provider_name=self.name,
            model=self.model,
            payload={"extracted": text.strip()},
        )


@pytest.mark.asyncio
async def test_retry_metrics_and_chunk_replay_protection() -> None:
    provider = MockFlakyProvider()
    orchestrator = LLMOrchestrator(
        providers=[provider],
        max_retries=3,
        base_delay_seconds=0.01,
        max_delay_seconds=0.05,
    )

    # Multi-chunk text (> 4000 tokens simulation by mocking chunker)
    chunk1 = "Chunk 1: OpenAI research overview."
    chunk2 = "Chunk 2: Anthropic alignment models."

    # Manually pass chunker with max 5 tokens to force 2 chunks
    orchestrator.chunker.max_tokens_per_chunk = 5

    text = f"{chunk1}\n\n{chunk2}"
    res = await orchestrator.extract(schema_name="startup", text=text, source_url="https://example.com")

    assert isinstance(res, LLMProviderResult)
    assert res.provider_name == "flaky"
    assert res.chunk_count > 1
    assert "extracted" in res.payload

    # Verify chunk 1 was attempted 2 times (retry after 429 succeeded)
    assert provider.chunk_attempts[chunk1] == 2

    # Verify chunk 2 was attempted 2 times (413 retry succeeded without re-processing chunk 1!)
    assert provider.chunk_attempts[chunk2] == 2
