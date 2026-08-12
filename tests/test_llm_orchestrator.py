"""Tests for LLMOrchestrator fallback chain, caching, and confidence scoring."""

import pytest

from ai_intel.llm import LLMError, LLMOrchestrator, LLMProvider, LLMProviderResult, MockLLMProvider
from ai_intel.schemas.records import ProductContent


class FailingLLMProvider(LLMProvider):
    name = "failing"
    model = "failing-model"
    tier = 1

    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        raise LLMError("API failure", status_code=500, retryable=False)


@pytest.mark.asyncio
async def test_orchestrator_fallback_chain() -> None:
    failing_provider = FailingLLMProvider()
    mock_provider = MockLLMProvider()

    orchestrator = LLMOrchestrator(providers=[failing_provider, mock_provider])
    res = await orchestrator.extract(schema_name="startup", text="OpenAI description", source_url="https://openai.com")

    assert isinstance(res, LLMProviderResult)
    assert res.provider_name == "mock"  # Fallback to secondary succeeded
    assert res.payload["entityName"] == "Mocked AI Corp"
    assert res.confidence_score == 0.50  # Mock provider (tier 4) base score


@pytest.mark.asyncio
async def test_orchestrator_caching() -> None:
    mock_provider = MockLLMProvider()
    orchestrator = LLMOrchestrator(providers=[mock_provider])

    # First call -> cache miss
    res1 = await orchestrator.extract(schema_name="product", text="GPT-4 assistant", source_url="https://chatgpt.com")
    assert isinstance(res1, LLMProviderResult)
    assert res1.cache_hit is False

    # Second call -> cache hit
    res2 = await orchestrator.extract(schema_name="product", text="GPT-4 assistant", source_url="https://chatgpt.com")
    assert isinstance(res2, LLMProviderResult)
    assert res2.cache_hit is True
    assert res2.confidence_score == 1.0


@pytest.mark.asyncio
async def test_orchestrator_output_model_validation() -> None:
    mock_provider = MockLLMProvider()
    orchestrator = LLMOrchestrator(providers=[mock_provider])

    # Extract directly into ProductContent schema
    content = await orchestrator.extract(
        schema_name="product",
        text="ChatGPT Assistant",
        source_url="https://chatgpt.com",
        output_model=ProductContent,
    )
    assert isinstance(content, ProductContent)
    assert content.product_name == "Mocked Assistant Pro"
