"""Tests for JobPipeline execution, natural key hierarchy, and entity resolution."""

from datetime import datetime, timedelta, timezone

import pytest

from ai_intel.config import Settings
from ai_intel.pipelines.jobs import JobPipeline
from ai_intel.schemas import JobCandidate
from ai_intel.storage import InMemoryStorageRepository


class DummyJobCrawler:
    def __init__(self, source_name: str, candidates: list[JobCandidate]) -> None:
        self.source_name = source_name
        self.candidates = candidates

    async def fetch_jobs(self, session: object, limit: int) -> list[JobCandidate]:
        return self.candidates[:limit]


@pytest.mark.asyncio
async def test_job_pipeline_execution_and_natural_keys() -> None:
    now_dt = datetime.now(timezone.utc)
    fresh_dt = now_dt - timedelta(hours=2)
    stale_dt = now_dt - timedelta(hours=36)

    # 1. Company domain present -> natural_key = job:company:<domain>:role:<norm_role>
    c1 = JobCandidate(
        role_title="Senior ML Engineer (Remote)",
        raw_company_name="OpenAI, Inc.",
        company_domain="openai.com",
        source_name="AIJobs.com",
        source_url="https://aijobs.com/job/1",
        is_remote=True,
        posted_date=fresh_dt,
        source_job_id="job-101",
    )
    # 2. Duplicate candidate (should be deduped by domain + role)
    c2 = JobCandidate(
        role_title="Senior ML Engineer",
        raw_company_name="OpenAI",
        company_domain="openai.com",
        source_name="RemoteOK AI",
        source_url="https://remoteok.com/job/101",
        is_remote=True,
        posted_date=fresh_dt,
    )
    # 3. Stale candidate -> should be rejected by 24h filter
    c3 = JobCandidate(
        role_title="Stale Research Assistant",
        raw_company_name="Acme AI Lab",
        source_name="Jobicy AI",
        source_url="https://jobicy.com/stale-job",
        posted_date=stale_dt,
    )

    storage = InMemoryStorageRepository()
    pipeline = JobPipeline(
        settings=Settings(app_env="test"),
        storage=storage,
        crawlers=[
            DummyJobCrawler("AIJobs.com", [c1, c2]),
            DummyJobCrawler("Jobicy AI", [c3]),
        ],
    )

    result = await pipeline.ingest(hours=24, limit=10, session=object())

    assert result.requested_limit == 10
    assert result.cutoff_hours == 24
    assert result.fetched_jobs == 3
    assert result.stored_jobs == 1  # c1 stored, c2 deduped, c3 rejected_stale
    assert result.rejected_stale == 1
    assert result.failures == 0

    # Verify natural key evaluation
    rec = list(storage.records.values())[0]
    assert rec.natural_key() == "job:company:openai.com:role:senior ml engineer"
    assert rec.content.company == "OpenAI"  # Resolved canonical name
    assert rec.content.raw_company == "OpenAI, Inc."  # Preserved raw vendor name
    assert rec.content.role_family == "ML Engineer"
    assert rec.content.posted_date == fresh_dt
    assert rec.content.first_seen_at is not None

    # Mappings recorded
    assert len(storage.mappings) == 1
