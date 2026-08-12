"""AI Job ingestion pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from ai_intel.config import Settings
from ai_intel.crawlers.jobs import (
    AIJobsCrawler,
    JobicyCrawler,
    MachineLearningJobsCrawler,
    RemoteOKCrawler,
    WellfoundJobsCrawler,
    classify_role_family,
    normalize_role_title,
)
from ai_intel.logging import get_logger
from ai_intel.resolution import EntityResolver
from ai_intel.schemas import EntityMappingLog, JobCandidate, JobIngestionResult, JobRecord
from ai_intel.schemas.base import SourceRef
from ai_intel.storage.base import StorageRepository
from ai_intel.validation import RecordValidator

logger = get_logger(__name__)

try:
    import aiohttp  # type: ignore[import-not-found,import-untyped]
except ImportError:
    aiohttp = None  # type: ignore[assignment]


class JobCrawlerProtocol(Protocol):
    async def fetch_jobs(self, session: Any, limit: int) -> list[JobCandidate]:
        ...


class JobPipeline:
    def __init__(
        self,
        settings: Settings,
        storage: StorageRepository,
        crawlers: list[JobCrawlerProtocol] | None = None,
        resolver: EntityResolver | None = None,
        validator: RecordValidator | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.crawlers = crawlers or [
            AIJobsCrawler(settings),
            WellfoundJobsCrawler(settings),
            MachineLearningJobsCrawler(settings),
            JobicyCrawler(settings),
            RemoteOKCrawler(settings),
        ]
        self.resolver = resolver or EntityResolver()
        self.validator = validator or RecordValidator()

    async def ingest(
        self,
        hours: int = 24,
        limit: int = 1000,
        run_id: str | None = None,
        session: Any | None = None,
    ) -> JobIngestionResult:
        run_id = run_id or f"jobs-{uuid4()}"
        source_counts: dict[str, int] = {}
        await self.storage.start_pipeline_run(run_id, source_counts=source_counts)

        owns_session = session is None
        if session is None:
            if aiohttp is None:
                raise RuntimeError("aiohttp is required for HTTP fetching. Install it with pip install aiohttp.")

            timeout = aiohttp.ClientTimeout(total=self.settings.default_http_timeout_seconds)
            connector = aiohttp.TCPConnector(ssl=False)
            session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": self.settings.crawl_user_agent},
            )

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        stored_jobs = 0
        resolved_companies = 0
        rejected_stale = 0
        failures = 0
        per_crawler_limit = max(1, limit // len(self.crawlers))

        try:
            results = await asyncio.gather(
                *(crawler.fetch_jobs(session, per_crawler_limit) for crawler in self.crawlers),
                return_exceptions=True,
            )

            all_candidates: list[JobCandidate] = []
            for crawler, res in zip(self.crawlers, results):
                name = getattr(crawler, "source_name", "unknown_crawler")
                if isinstance(res, BaseException):
                    logger.warning("job_crawler_failed", extra={"run_id": run_id, "crawler": name, "error": str(res)})
                    source_counts[name] = 0
                elif isinstance(res, list):
                    source_counts[name] = len(res)
                    all_candidates.extend(res)

            seen_natural_keys: set[str] = set()
            for candidate in all_candidates:
                try:
                    posted_date = candidate.posted_date or candidate.source_collected_at
                    if posted_date < cutoff_time:
                        rejected_stale += 1
                        continue

                    record, was_resolved = self._build_record(candidate, posted_date)
                    nat_key = record.natural_key()
                    if nat_key in seen_natural_keys:
                        continue
                    seen_natural_keys.add(nat_key)

                    if was_resolved:
                        resolved_companies += 1

                    self.validator.validate(record)
                    mapping = getattr(record, "_mapping_log", None)
                    if mapping is not None:
                        await self.storage.log_mapping(mapping)

                    if await self.storage.upsert_job(record):
                        stored_jobs += 1
                        if stored_jobs >= limit:
                            break
                except Exception as exc:
                    failures += 1
                    logger.warning(
                        "job_ingest_failed",
                        extra={"run_id": run_id, "role": candidate.role_title, "error": str(exc)},
                    )

            await self.storage.complete_pipeline_run(
                run_id,
                source_counts=source_counts,
                success_counts={"jobs": stored_jobs},
                failure_counts={"jobs": failures + rejected_stale},
            )

            return JobIngestionResult(
                requested_limit=limit,
                cutoff_hours=hours,
                fetched_jobs=len(all_candidates),
                stored_jobs=stored_jobs,
                resolved_companies=resolved_companies,
                rejected_stale=rejected_stale,
                failures=failures,
            )
        finally:
            if owns_session:
                await session.close()

    def _build_record(self, candidate: JobCandidate, posted_date: datetime) -> tuple[JobRecord, bool]:
        resolution = self.resolver.resolve(candidate.raw_company_name, entity_type="startup")
        is_confident = resolution.is_resolved and resolution.confidence >= 0.8
        canonical_company = resolution.canonical_name if is_confident else candidate.raw_company_name
        method = resolution.method if is_confident else "raw_company_preserved"
        confidence = resolution.confidence if is_confident else 1.0

        normalized_role = normalize_role_title(candidate.role_title)
        role_family = classify_role_family(candidate.role_title, candidate.description)
        now_dt = datetime.now(timezone.utc)

        record = JobRecord(
            source=SourceRef(name=candidate.source_name, url=candidate.source_url),
            collectedAt=candidate.source_collected_at or now_dt,
            content={
                "company": canonical_company or candidate.raw_company_name,
                "rawCompany": candidate.raw_company_name,
                "companyDomain": candidate.company_domain,
                "roleTitle": candidate.role_title,
                "normalizedRole": normalized_role,
                "roleFamily": role_family,
                "location": candidate.location,
                "isRemote": candidate.is_remote,
                "employmentType": candidate.employment_type,
                "salaryText": candidate.salary_text,
                "description": candidate.description or candidate.role_title,
                "postedDate": posted_date,
                "firstSeenAt": candidate.source_collected_at or now_dt,
                "sourceJobId": candidate.source_job_id,
                "sourceName": candidate.source_name,
                "sourceUrl": candidate.source_url,
            },
        )
        mapping = EntityMappingLog(
            raw_name=candidate.raw_company_name,
            canonical_name=canonical_company,
            canonical_id=resolution.canonical_id,
            entity_type="startup",
            confidence=confidence,
            method=method,
            resolution_tier=resolution.resolution_tier,
            signals_evaluated=resolution.signals_evaluated,
            source_url=candidate.source_url,
        )
        record.__dict__["_mapping_log"] = mapping
        return record, is_confident


async def run_job_ingestion(
    settings: Settings,
    storage: StorageRepository,
    hours: int = 24,
    limit: int = 1000,
) -> JobIngestionResult:
    pipeline = JobPipeline(settings=settings, storage=storage)
    return await pipeline.ingest(hours=hours, limit=limit)
