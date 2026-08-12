"""Storage abstraction used by pipeline workers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ai_intel.schemas import CrawlTarget, EntityMappingLog, RawDocument, RecordEnvelope
from ai_intel.schemas.research import GitHubRepoMetrics
from ai_intel.schemas.records import JobRecord, NewsRecord, ProductRecord, ResearchPaperRecord, StartupRecord


class StorageRepository(ABC):
    @abstractmethod
    async def enqueue(self, target: CrawlTarget) -> bool:
        """Add target if not already seen. Returns True when inserted."""
        raise NotImplementedError

    @abstractmethod
    async def claim_batch(self, limit: int) -> list[CrawlTarget]:
        raise NotImplementedError

    @abstractmethod
    async def save_raw(self, raw: RawDocument) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def upsert_record(self, record: RecordEnvelope) -> bool:
        """Upsert canonical record. Returns True when newly inserted."""
        raise NotImplementedError

    @abstractmethod
    async def log_mapping(self, mapping: EntityMappingLog) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_done(self, target: CrawlTarget) -> None:
        raise NotImplementedError

    async def start_pipeline_run(self, run_id: str, source_counts: dict[str, int] | None = None) -> None:
        """Record the start of an auditable pipeline run."""
        raise NotImplementedError

    async def complete_pipeline_run(
        self,
        run_id: str,
        success_counts: dict[str, int],
        failure_counts: dict[str, int],
        export_status: str = "not_started",
        source_counts: dict[str, int] | None = None,
    ) -> None:
        """Record completion counts for an auditable pipeline run."""
        raise NotImplementedError

    async def upsert_research_paper(self, record: ResearchPaperRecord) -> bool:
        raise NotImplementedError

    async def upsert_github_metrics(self, metrics: GitHubRepoMetrics) -> bool:
        raise NotImplementedError

    async def upsert_startup(self, record: StartupRecord) -> bool:
        raise NotImplementedError

    async def upsert_product(self, record: ProductRecord) -> bool:
        raise NotImplementedError

    async def upsert_news(self, record: NewsRecord) -> bool:
        raise NotImplementedError

    async def upsert_job(self, record: JobRecord) -> bool:
        raise NotImplementedError

    async def batch_upsert_startups(self, records: list[StartupRecord]) -> int:
        count = 0
        for r in records:
            if await self.upsert_startup(r):
                count += 1
        return count

    async def batch_upsert_products(self, records: list[ProductRecord]) -> int:
        count = 0
        for r in records:
            if await self.upsert_product(r):
                count += 1
        return count

    async def batch_upsert_papers(self, records: list[ResearchPaperRecord]) -> int:
        count = 0
        for r in records:
            if await self.upsert_research_paper(r):
                count += 1
        return count

    async def batch_upsert_jobs(self, records: list[JobRecord]) -> int:
        count = 0
        for r in records:
            if await self.upsert_job(r):
                count += 1
        return count

    async def batch_upsert_news(self, records: list[NewsRecord]) -> int:
        count = 0
        for r in records:
            if await self.upsert_news(r):
                count += 1
        return count
