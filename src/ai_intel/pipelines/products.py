"""Product ingestion pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from ai_intel.crawlers.products import (
    AIValleyCrawler,
    AIxploriaCrawler,
    FuturepediaCrawler,
    HuggingFaceSpacesCrawler,
    TopAIToolsCrawler,
)
from ai_intel.logging import get_logger
from ai_intel.resolution import EntityResolver
from ai_intel.schemas import EntityMappingLog, ProductCandidate, ProductIngestionResult, ProductRecord
from ai_intel.schemas.base import SourceRef
from ai_intel.storage.base import StorageRepository
from ai_intel.validation import RecordValidator

logger = get_logger(__name__)


try:
    import aiohttp  # type: ignore[import-not-found,import-untyped]
except ImportError:
    aiohttp = None  # type: ignore[assignment]


class ProductCrawlerProtocol(Protocol):
    async def fetch_products(self, session: Any, limit: int) -> list[ProductCandidate]:
        ...


class ProductPipeline:
    def __init__(
        self,
        settings: Settings,
        storage: StorageRepository,
        crawlers: list[ProductCrawlerProtocol] | None = None,
        resolver: EntityResolver | None = None,
        validator: RecordValidator | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.crawlers = crawlers or [
            HuggingFaceSpacesCrawler(settings),
            AIxploriaCrawler(settings),
            AIValleyCrawler(settings),
            FuturepediaCrawler(settings),
            TopAIToolsCrawler(settings),
        ]
        self.resolver = resolver or EntityResolver()
        self.validator = validator or RecordValidator()

    async def ingest(
        self,
        limit: int,
        run_id: str | None = None,
        session: Any | None = None,
    ) -> ProductIngestionResult:
        run_id = run_id or f"products-{uuid4()}"
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
        resolved_startups = 0
        per_crawler_limit = max(1, limit // len(self.crawlers))

        try:
            results = await asyncio.gather(
                *(crawler.fetch_products(session, per_crawler_limit) for crawler in self.crawlers),
                return_exceptions=True,
            )

            all_candidates: list[ProductCandidate] = []
            for crawler, res in zip(self.crawlers, results):
                name = getattr(crawler, "source_name", "unknown_crawler")
                if isinstance(res, BaseException):
                    logger.warning("product_crawler_failed", extra={"run_id": run_id, "crawler": name, "error": str(res)})
                    source_counts[name] = 0
                elif isinstance(res, list):
                    source_counts[name] = len(res)
                    all_candidates.extend(res)

            seen_natural_keys: set[str] = set()
            for candidate in all_candidates:
                try:
                    record, was_resolved = self._build_record(candidate)
                    nat_key = record.natural_key()
                    if nat_key in seen_natural_keys:
                        continue
                    seen_natural_keys.add(nat_key)

                    if was_resolved:
                        resolved_startups += 1

                    self.validator.validate(record)
                    mapping = getattr(record, "_mapping_log", None)
                    if mapping is not None:
                        await self.storage.log_mapping(mapping)

                    if await self.storage.upsert_product(record):
                        stored += 1
                        if stored >= limit:
                            break
                except Exception as exc:
                    failures += 1
                    logger.warning(
                        "product_ingest_failed",
                        extra={"run_id": run_id, "product": candidate.product_name, "error": str(exc)},
                    )

            await self.storage.complete_pipeline_run(
                run_id,
                source_counts=source_counts,
                success_counts={"products": stored},
                failure_counts={"products": failures},
            )
            return ProductIngestionResult(
                requested_limit=limit,
                fetched_products=len(all_candidates),
                stored_products=stored,
                resolved_startups=resolved_startups,
                failures=failures,
            )
        finally:
            if owns_session:
                await session.close()

    def _build_record(self, candidate: ProductCandidate) -> tuple[ProductRecord, bool]:
        resolution = self.resolver.resolve(candidate.raw_startup_name, entity_type="startup")
        is_confident = resolution.is_resolved and resolution.confidence >= 0.8

        if is_confident:
            canonical_vendor = resolution.canonical_name or candidate.raw_startup_name
            canonical_id = resolution.canonical_id
            method = resolution.method
            confidence = resolution.confidence
            tier = resolution.resolution_tier
        else:
            canonical_vendor = ""  # Leave blank for unresolved entities to prevent false mapping
            canonical_id = ""
            method = "unresolved"
            confidence = 0.0
            tier = "UNRESOLVED"

        record = ProductRecord(
            source=SourceRef(name=candidate.source_name, url=candidate.source_url),
            collectedAt=candidate.source_collected_at or datetime.now(timezone.utc),
            content={
                "productName": candidate.product_name,
                "startupName": canonical_vendor,
                "rawStartupName": candidate.raw_startup_name,
                "pricingModel": candidate.pricing_model,
                "category": candidate.category,
                "sourceUrl": candidate.source_url,
            },
        )
        mapping = EntityMappingLog(
            raw_name=candidate.raw_startup_name,
            canonical_name=canonical_vendor,
            canonical_id=canonical_id,
            entity_type="startup",
            confidence=confidence,
            method=method,
            resolution_tier=tier,
            signals_evaluated=resolution.signals_evaluated,
            source_url=candidate.source_url,
        )
        record.__dict__["_mapping_log"] = mapping
        return record, is_confident


async def run_product_ingestion(
    settings: Settings,
    storage: StorageRepository,
    limit: int,
) -> ProductIngestionResult:
    pipeline = ProductPipeline(settings=settings, storage=storage)
    return await pipeline.ingest(limit=limit)
