"""Tests for Startup Pipeline end-to-end flow."""

import pytest

from ai_intel.config import Settings
from ai_intel.pipelines.startups import StartupPipeline
from ai_intel.schemas import StartupCandidate, StartupEnrichment, StartupRecord
from ai_intel.storage import InMemoryStorageRepository


class DummyYCCrawler:
    def __init__(self, candidates: list[StartupCandidate]) -> None:
        self.candidates = candidates

    async def fetch_startups(self, session: object, limit: int) -> list[StartupCandidate]:
        return self.candidates[:limit]


class DummyWellfoundEnricher:
    def __init__(self, enrichments: dict[str, StartupEnrichment]) -> None:
        self.enrichments = enrichments

    async def fetch_enrichments(self, session: object) -> dict[str, StartupEnrichment]:
        return self.enrichments


@pytest.mark.asyncio
async def test_startup_pipeline_ingest_flow() -> None:
    candidate1 = StartupCandidate(
        raw_name="OpenAI, Inc.",
        source_name="Y Combinator",
        source_url="https://www.ycombinator.com/companies/openai",
        website_url="https://openai.com",
        company_domain="openai.com",
        employee_count=1000,
        employee_count_raw="1000",
        batch="W16",
        industry="AI",
    )
    candidate2 = StartupCandidate(
        raw_name="OpenAI, Inc.",  # Duplicate entity to test deduping
        source_name="Y Combinator",
        source_url="https://www.ycombinator.com/companies/openai-dup",
    )
    candidate3 = StartupCandidate(
        raw_name="Acme Robotics",
        source_name="Y Combinator",
        source_url="https://www.ycombinator.com/companies/acme-robotics",
        employee_count=None,
        employee_count_raw=None,
    )

    wellfound_key = "acmerobotics"
    enrichment3 = StartupEnrichment(
        raw_name="Acme Robotics",
        source_name="Wellfound",
        source_url="https://wellfound.com/jobs",
        employee_count=None,
        employee_count_raw="11-50 employees",
    )

    storage = InMemoryStorageRepository()
    pipeline = StartupPipeline(
        settings=Settings(app_env="test"),
        storage=storage,
        yc_crawler=DummyYCCrawler([candidate1, candidate2, candidate3]),
        wellfound_enricher=DummyWellfoundEnricher({wellfound_key: enrichment3}),
    )

    result = await pipeline.ingest(limit=10, session=object())

    assert result.requested_limit == 10
    assert result.fetched_startups == 3
    assert result.enriched_startups == 1
    assert result.stored_startups == 2  # OpenAI deduped, Acme stored
    assert result.failures == 0

    assert len(storage.records) == 2
    openai_record = storage.records["startup:domain:openai.com"]
    assert openai_record.content.entity_name == "OpenAI"
    assert openai_record.content.data.employee_count == 1000

    acme_record = storage.records["startup:yc:acme-robotics"]
    assert acme_record.content.entity_name == "Acme Robotics"
    assert acme_record.content.data.employee_count is None
    assert acme_record.content.data.employee_count_raw == "11-50 employees"

    # Mapping logs were recorded
    assert len(storage.mappings) == 2


def test_startup_natural_key_hierarchy() -> None:
    # 1. Company Domain
    r1 = StartupRecord(
        source={"name": "Y Combinator", "url": "https://www.ycombinator.com/companies/stripe"},
        content={
            "entityName": "Stripe",
            "data": {"companyDomain": "stripe.com", "websiteUrl": "https://stripe.com"},
        },
    )
    assert r1.natural_key() == "startup:domain:stripe.com"

    # 2. YC Slug
    r2 = StartupRecord(
        source={"name": "Y Combinator", "url": "https://www.ycombinator.com/companies/stripe"},
        content={"entityName": "Stripe", "data": {}},
    )
    assert r2.natural_key() == "startup:yc:stripe"

    # 3. Source URL
    r3 = StartupRecord(
        source={"name": "Directory", "url": "https://example.com/startups/stripe"},
        content={"entityName": "Stripe", "data": {}},
    )
    assert r3.natural_key() == "startup:url:https://example.com/startups/stripe"

    # 4. Normalized Name fallback
    r4 = StartupRecord(
        source=None,
        content={"entityName": "Stripe", "data": {}},
    )
    assert r4.natural_key() == "startup:name:stripe"
