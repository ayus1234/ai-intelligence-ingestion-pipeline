"""In-memory storage implementation for tests and local dry-runs."""

from __future__ import annotations

from collections import deque

from ai_intel.schemas import CrawlTarget, EntityMappingLog, RawDocument, RecordEnvelope
from ai_intel.schemas.records import JobRecord, NewsRecord, ProductRecord, ResearchPaperRecord, StartupRecord
from ai_intel.schemas.research import GitHubRepoMetrics
from ai_intel.storage.base import StorageRepository
from ai_intel.utils.hashing import sha256_text
from ai_intel.utils.urls import normalize_url


class InMemoryStorageRepository(StorageRepository):
    def __init__(self) -> None:
        self._queued_hashes: set[str] = set()
        self._done_hashes: set[str] = set()
        self._queue: deque[CrawlTarget] = deque()
        self.raw_documents: dict[str, RawDocument] = {}
        self.records: dict[str, RecordEnvelope] = {}
        self.mappings: list[EntityMappingLog] = []
        self.github_metrics: dict[str, GitHubRepoMetrics] = {}
        self.pipeline_runs: dict[str, dict[str, object]] = {}

    async def enqueue(self, target: CrawlTarget) -> bool:
        key = sha256_text(normalize_url(str(target.url)))
        if key in self._queued_hashes or key in self._done_hashes:
            return False
        self._queued_hashes.add(key)
        self._queue.append(target)
        return True

    async def claim_batch(self, limit: int) -> list[CrawlTarget]:
        claimed: list[CrawlTarget] = []
        while self._queue and len(claimed) < limit:
            claimed.append(self._queue.popleft())
        return claimed

    async def save_raw(self, raw: RawDocument) -> bool:
        if raw.content_hash in self.raw_documents:
            return False
        self.raw_documents[raw.content_hash] = raw
        return True

    async def upsert_record(self, record: RecordEnvelope) -> bool:
        key = record.natural_key()
        is_new = key not in self.records
        self.records[key] = record
        return is_new

    async def log_mapping(self, mapping: EntityMappingLog) -> None:
        self.mappings.append(mapping)

    async def mark_done(self, target: CrawlTarget) -> None:
        key = sha256_text(normalize_url(str(target.url)))
        self._done_hashes.add(key)

    async def start_pipeline_run(self, run_id: str, source_counts: dict[str, int] | None = None) -> None:
        self.pipeline_runs[run_id] = {
            "status": "running",
            "source_counts": source_counts or {},
            "success_counts": {},
            "failure_counts": {},
            "export_status": "not_started",
        }

    async def complete_pipeline_run(
        self,
        run_id: str,
        success_counts: dict[str, int],
        failure_counts: dict[str, int],
        export_status: str = "not_started",
        source_counts: dict[str, int] | None = None,
    ) -> None:
        manifest = self.pipeline_runs.setdefault(run_id, {})
        manifest.update(
            {
                "status": "completed",
                "source_counts": source_counts or manifest.get("source_counts", {}),
                "success_counts": success_counts,
                "failure_counts": failure_counts,
                "export_status": export_status,
            }
        )

    async def upsert_research_paper(self, record: ResearchPaperRecord) -> bool:
        return await self.upsert_record(record)

    async def upsert_github_metrics(self, metrics: GitHubRepoMetrics) -> bool:
        key = str(metrics.github_url)
        is_new = key not in self.github_metrics
        self.github_metrics[key] = metrics
        return is_new

    async def upsert_startup(self, record: StartupRecord) -> bool:
        return await self.upsert_record(record)

    async def upsert_product(self, record: ProductRecord) -> bool:
        return await self.upsert_record(record)

    async def upsert_news(self, record: NewsRecord) -> bool:
        return await self.upsert_record(record)

    async def upsert_job(self, record: JobRecord) -> bool:
        return await self.upsert_record(record)
