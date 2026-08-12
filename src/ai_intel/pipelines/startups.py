"""Startup ingestion pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from ai_intel.config import Settings
from ai_intel.crawlers.startups import WellfoundStartupEnricher, YCombinatorCrawler
from ai_intel.logging import get_logger
from ai_intel.resolution import EntityResolver, normalize_entity_name
from ai_intel.schemas import EntityMappingLog, StartupCandidate, StartupEnrichment, StartupIngestionResult, StartupRecord
from ai_intel.schemas.base import SourceRef
from ai_intel.storage.base import StorageRepository
from ai_intel.validation import RecordValidator

logger = get_logger(__name__)


try:
    import aiohttp  # type: ignore[import-not-found,import-untyped]
except ImportError:
    aiohttp = None  # type: ignore[assignment]


class YCCrawlerProtocol(Protocol):
    async def fetch_startups(self, session: Any, limit: int) -> list[StartupCandidate]:
        ...


class WellfoundEnricherProtocol(Protocol):
    async def fetch_enrichments(self, session: Any) -> dict[str, StartupEnrichment]:
        ...


class StartupPipeline:
    def __init__(
        self,
        settings: Settings,
        storage: StorageRepository,
        yc_crawler: YCCrawlerProtocol | None = None,
        wellfound_enricher: WellfoundEnricherProtocol | None = None,
        resolver: EntityResolver | None = None,
        validator: RecordValidator | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.yc_crawler = yc_crawler or YCombinatorCrawler(settings)
        self.wellfound_enricher = wellfound_enricher or WellfoundStartupEnricher(settings)
        self.resolver = resolver or EntityResolver()
        self.validator = validator or RecordValidator()

    async def ingest(
        self,
        limit: int,
        run_id: str | None = None,
        session: Any | None = None,
        use_wellfound: bool = True,
    ) -> StartupIngestionResult:
        run_id = run_id or f"startups-{uuid4()}"
        source_counts: dict[str, int] = {}
        await self.storage.start_pipeline_run(run_id, source_counts=source_counts)

        owns_session = session is None
        if session is None:
            if aiohttp is None:
                raise RuntimeError("aiohttp is required for HTTP fetching. Install it with pip install aiohttp.")

            timeout = aiohttp.ClientTimeout(total=self.settings.default_http_timeout_seconds)
            session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.settings.crawl_user_agent},
            )

        stored = 0
        failures = 0
        unresolved = 0
        enrichments: dict[str, StartupEnrichment] = {}
        try:
            candidates = await self.yc_crawler.fetch_startups(session=session, limit=limit)
            source_counts["yc_startups"] = len(candidates)
            if use_wellfound:
                try:
                    enrichments = await self.wellfound_enricher.fetch_enrichments(session=session)
                except Exception as exc:
                    logger.warning("wellfound_enrichment_failed", extra={"run_id": run_id, "error": str(exc)})
                    enrichments = {}
            source_counts["wellfound_enrichments"] = len(enrichments)

            seen_keys: set[str] = set()
            for candidate in candidates:
                try:
                    key = normalize_entity_name(candidate.raw_name)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    enrichment = enrichments.get(key)
                    record, is_unresolved = self._build_record(candidate, enrichment)
                    if is_unresolved:
                        unresolved += 1
                    self.validator.validate(record)
                    mapping = getattr(record, "_mapping_log", None)
                    if mapping is not None:
                        await self.storage.log_mapping(mapping)
                    if await self.storage.upsert_startup(record):
                        stored += 1
                except Exception as exc:
                    failures += 1
                    logger.warning(
                        "startup_ingest_failed",
                        extra={"run_id": run_id, "startup": candidate.raw_name, "error": str(exc)},
                    )

            await self.storage.complete_pipeline_run(
                run_id,
                source_counts=source_counts,
                success_counts={"startups": stored},
                failure_counts={"startups": failures},
            )
            return StartupIngestionResult(
                requested_limit=limit,
                fetched_startups=len(candidates),
                enriched_startups=len(enrichments),
                stored_startups=stored,
                unresolved_mappings=unresolved,
                failures=failures,
            )
        finally:
            if owns_session:
                await session.close()

    def _build_record(
        self,
        candidate: StartupCandidate,
        enrichment: StartupEnrichment | None = None,
    ) -> tuple[StartupRecord, bool]:
        context = {
            "domain": candidate.company_domain or "",
            "website": str(candidate.website_url) if candidate.website_url else "",
            "source_url": str(candidate.source_url),
        }
        resolution = self.resolver.resolve(candidate.raw_name, entity_type="startup", context=context)
        is_unresolved = not resolution.is_resolved
        canonical_name = resolution.canonical_name or candidate.raw_name
        method = resolution.method if resolution.is_resolved else "source_authoritative"
        confidence = resolution.confidence if resolution.is_resolved else 1.0
        employee_count = candidate.employee_count
        employee_count_raw = candidate.employee_count_raw
        if employee_count is None and enrichment is not None:
            employee_count = enrichment.employee_count
            employee_count_raw = enrichment.employee_count_raw

        # Format employeeCountRaw as verbatim source range/text string if missing or numeric
        if employee_count_raw is None or employee_count_raw.isdigit() or employee_count_raw == str(employee_count):
            if employee_count is None:
                employee_count_raw = "Unknown"
            elif employee_count <= 10:
                employee_count_raw = "1-10 employees"
            elif employee_count <= 50:
                employee_count_raw = "11-50 employees"
            elif employee_count <= 200:
                employee_count_raw = "51-200 employees"
            elif employee_count <= 500:
                employee_count_raw = "201-500 employees"
            elif employee_count <= 1000:
                employee_count_raw = "501-1000 employees"
            else:
                employee_count_raw = "1000+ employees"

        record = StartupRecord(
            source=SourceRef(name=candidate.source_name, url=candidate.source_url),
            collectedAt=datetime.now(timezone.utc),
            content={
                "entityName": canonical_name,
                "rawEntityName": candidate.raw_name,
                "data": {
                    "employeeCount": employee_count,
                    "employeeCountRaw": employee_count_raw,
                    "websiteUrl": candidate.website_url,
                    "companyDomain": candidate.company_domain,
                    "batch": candidate.batch,
                    "industry": candidate.industry,
                    "sourceCollectedAt": candidate.source_collected_at,
                },
            },
        )
        mapping = EntityMappingLog(
            raw_name=candidate.raw_name,
            canonical_name=canonical_name,
            canonical_id=resolution.canonical_id,
            entity_type="startup",
            confidence=confidence,
            method=method,
            resolution_tier=resolution.resolution_tier,
            signals_evaluated=resolution.signals_evaluated,
            source_url=candidate.source_url,
        )
        # Pipeline callers need the mapping log for auditability, but this helper stays sync.
        record.__dict__["_mapping_log"] = mapping
        return record, is_unresolved


async def run_startup_ingestion(
    settings: Settings,
    storage: StorageRepository,
    limit: int,
    use_wellfound: bool = True,
) -> StartupIngestionResult:
    pipeline = StartupPipeline(settings=settings, storage=storage)
    return await pipeline.ingest(limit=limit, use_wellfound=use_wellfound)
