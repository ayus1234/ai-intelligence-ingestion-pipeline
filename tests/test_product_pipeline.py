"""Tests for Product Pipeline end-to-end flow."""

import pytest

from ai_intel.config import Settings
from ai_intel.pipelines.products import ProductPipeline
from ai_intel.schemas import ProductCandidate
from ai_intel.schemas.records import PricingModel
from ai_intel.storage import InMemoryStorageRepository


class DummyProductCrawler:
    def __init__(self, source_name: str, candidates: list[ProductCandidate]) -> None:
        self.source_name = source_name
        self.candidates = candidates

    async def fetch_products(self, session: object, limit: int) -> list[ProductCandidate]:
        return self.candidates[:limit]


@pytest.mark.asyncio
async def test_product_pipeline_ingest_flow() -> None:
    c1 = ProductCandidate(
        product_name="ChatGPT Plus",
        raw_startup_name="OpenAI, Inc.",  # Resolved to canonical 'OpenAI'
        source_name="AIxploria",
        source_url="https://www.aixploria.com/chatgpt",
        pricing_model=PricingModel.PAID,
        category="Chatbots",
    )
    c2 = ProductCandidate(
        product_name="ChatGPT Plus",  # Duplicate product by source_url/natural_key
        raw_startup_name="OpenAI, Inc.",
        source_name="AIxploria",
        source_url="https://www.aixploria.com/chatgpt",
        pricing_model=PricingModel.PAID,
    )
    c3 = ProductCandidate(
        product_name="Custom Vendor Tool",
        raw_startup_name="Unregistered Acme Tech",  # Unresolved -> preserves raw startup name
        source_name="Futurepedia",
        source_url="https://www.futurepedia.io/acme-tool",
        pricing_model=PricingModel.FREE,
    )

    storage = InMemoryStorageRepository()
    pipeline = ProductPipeline(
        settings=Settings(app_env="test"),
        storage=storage,
        crawlers=[
            DummyProductCrawler("AIxploria", [c1, c2]),
            DummyProductCrawler("Futurepedia", [c3]),
        ],
    )

    result = await pipeline.ingest(limit=10, session=object())

    assert result.requested_limit == 10
    assert result.fetched_products == 3
    assert result.stored_products == 2  # c2 deduped
    assert result.failures == 0

    assert len(storage.records) == 2
    chatgpt_rec = storage.records["product:url:https://www.aixploria.com/chatgpt"]
    assert chatgpt_rec.content.product_name == "ChatGPT Plus"
    assert chatgpt_rec.content.startup_name == "OpenAI"
    assert chatgpt_rec.content.raw_startup_name == "OpenAI, Inc."

    acme_rec = storage.records["product:url:https://www.futurepedia.io/acme-tool"]
    assert acme_rec.content.product_name == "Custom Vendor Tool"
    assert acme_rec.content.startup_name == "Unregistered Acme Tech"
    assert acme_rec.content.raw_startup_name == "Unregistered Acme Tech"

    # Mappings recorded
    assert len(storage.mappings) == 2
