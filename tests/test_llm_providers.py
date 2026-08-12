"""Tests for LLM providers and provider-aware concurrency semaphores."""

import pytest

from ai_intel.llm import DeepSeekProvider, GeminiFlashProvider, GroqLlamaProvider, MockLLMProvider


def test_provider_concurrency_limits() -> None:
    gemini = GeminiFlashProvider()
    groq = GroqLlamaProvider()
    deepseek = DeepSeekProvider()
    mock = MockLLMProvider()

    assert gemini.concurrency_limit == 10
    assert groq.concurrency_limit == 20
    assert deepseek.concurrency_limit == 8
    assert mock.concurrency_limit == 50


@pytest.mark.asyncio
async def test_mock_llm_provider_extraction() -> None:
    provider = MockLLMProvider()
    schemas = ["startup", "product", "paper", "news", "job"]
    for s in schemas:
        res = await provider.extract(schema_name=s, text="Sample text", source_url="https://example.com")
        assert res.provider_name == "mock"
        assert res.payload is not None
        assert isinstance(res.payload, dict)
