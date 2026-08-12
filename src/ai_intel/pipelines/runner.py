"""Master Pipeline Runner executing all 5 verticals, LLM extraction, entity resolution, storage, data quality audit, and Google Sheets export."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from ai_intel.config import Settings, get_settings
from ai_intel.exporters.sheets import GoogleSheetsExporter
from ai_intel.logging import get_logger
from ai_intel.llm import LLMOrchestrator, MockLLMProvider
from ai_intel.metrics import metrics_collector
from ai_intel.pipelines.jobs import JobPipeline
from ai_intel.pipelines.news import NewsPipeline
from ai_intel.pipelines.products import ProductPipeline
from ai_intel.pipelines.research_papers import ResearchPaperPipeline
from ai_intel.pipelines.startups import StartupPipeline
from ai_intel.resolution import EntityResolver
from ai_intel.storage.base import StorageRepository
from ai_intel.storage.memory import InMemoryStorageRepository
from ai_intel.storage.postgres import PostgresStorageRepository
from ai_intel.validation.quality import DataQualityReport, DataQualityReporter

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MasterRunResult:
    run_id: str
    started_at: datetime
    completed_at: datetime
    status: str
    total_records: int
    vertical_counts: dict[str, int]
    export_destination: str
    quality_report: DataQualityReport


class MasterPipelineRunner:
    def __init__(
        self,
        settings: Settings | None = None,
        storage: StorageRepository | None = None,
        resolver: EntityResolver | None = None,
        exporter: GoogleSheetsExporter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage
        self.resolver = resolver or EntityResolver()
        self.exporter = exporter or GoogleSheetsExporter()

    async def run_all(
        self,
        hours: int = 24,
        limit: int = 1000,
        dry_run: bool = True,
        export_destination: str | None = None,
    ) -> MasterRunResult:
        run_id = f"run-all-{uuid4()}"
        started_at = datetime.now(timezone.utc)
        logger.info("master_pipeline_run_started", extra={"run_id": run_id, "hours": hours, "limit": limit, "dry_run": dry_run})

        owns_storage = self.storage is None
        if self.storage is None:
            if dry_run:
                storage: StorageRepository = InMemoryStorageRepository()
            else:
                try:
                    storage = PostgresStorageRepository(self.settings)
                    await storage.__aenter__()
                except Exception as exc:
                    logger.warning("postgres_connection_failed_falling_back_to_in_memory", extra={"error": str(exc)})
                    storage = InMemoryStorageRepository()
        else:
            storage = self.storage

        try:
            await storage.start_pipeline_run(run_id, source_counts={})

            # 1. Research Papers
            paper_pipeline = ResearchPaperPipeline(settings=self.settings, storage=storage)
            paper_res = await paper_pipeline.ingest(limit=limit, run_id=f"{run_id}-papers")

            # 2. Startups
            startup_pipeline = StartupPipeline(settings=self.settings, storage=storage, resolver=self.resolver)
            startup_res = await startup_pipeline.ingest(limit=limit, run_id=f"{run_id}-startups")

            # 3. Products
            product_pipeline = ProductPipeline(settings=self.settings, storage=storage, resolver=self.resolver)
            product_res = await product_pipeline.ingest(limit=limit, run_id=f"{run_id}-products")

            # 4. News
            news_pipeline = NewsPipeline(settings=self.settings, storage=storage)
            news_res = await news_pipeline.ingest(hours=hours, limit=limit, run_id=f"{run_id}-news")

            # 5. Jobs
            job_pipeline = JobPipeline(settings=self.settings, storage=storage, resolver=self.resolver)
            job_res = await job_pipeline.ingest(hours=hours, limit=limit, run_id=f"{run_id}-jobs")

            # 6. LLM Extraction Probe
            orchestrator = LLMOrchestrator(providers=[MockLLMProvider()])
            await orchestrator.extract(schema_name="startup", text="Master run sample extraction", source_url="https://example.com")
            metrics_collector.record_provider_status("mock", "success")

            # Collect records from storage for quality audit and export
            records_by_type: dict[str, list[Any]] = {
                "papers": [],
                "startups": [],
                "products": [],
                "news": [],
                "jobs": [],
            }

            type_map = {
                "startup": "startups",
                "startups": "startups",
                "product": "products",
                "products": "products",
                "research_paper": "papers",
                "paper": "papers",
                "papers": "papers",
                "news": "news",
                "job": "jobs",
                "jobs": "jobs",
            }

            if isinstance(storage, InMemoryStorageRepository):
                for rec in storage.records.values():
                    rtype = rec.record_type.value.lower()
                    target_key = type_map.get(rtype)
                    if target_key and target_key in records_by_type:
                        records_by_type[target_key].append(rec)

            # 7. Data Quality Audit Report
            quality_report = DataQualityReporter.audit_run(run_id=run_id, records_by_type=records_by_type, cutoff_hours=hours)

            # 8. Export to 6 required tabs / files
            dest = export_destination or f"exports/run_{run_id}"
            export_res = await self.exporter.export(
                run_id=run_id,
                destination=dest,
                storage=storage,
                records_by_type=records_by_type,
                quality_report=quality_report.model_dump(mode="json"),
            )
            quality_report.export_row_counts = export_res.row_counts

            completed_at = datetime.now(timezone.utc)

            vertical_counts = {
                "papers": paper_res.stored_papers,
                "startups": startup_res.stored_startups,
                "products": product_res.stored_products,
                "news": news_res.stored_articles,
                "jobs": job_res.stored_jobs,
            }
            total_stored = sum(vertical_counts.values())

            await storage.complete_pipeline_run(
                run_id=run_id,
                success_counts=vertical_counts,
                failure_counts={"papers": paper_res.failures, "startups": startup_res.failures},
                export_status="completed",
                source_counts={"total": total_stored},
            )

            logger.info(
                "master_pipeline_run_completed",
                extra={
                    "run_id": run_id,
                    "total_stored": total_stored,
                    "export_destination": export_res.destination,
                },
            )

            return MasterRunResult(
                run_id=run_id,
                started_at=started_at,
                completed_at=completed_at,
                status="COMPLETED",
                total_records=total_stored,
                vertical_counts=vertical_counts,
                export_destination=export_res.destination,
                quality_report=quality_report,
            )
        finally:
            if owns_storage and isinstance(storage, PostgresStorageRepository):
                await storage.__aexit__(None, None, None)


async def run_master_pipeline(
    hours: int = 24,
    limit: int = 1000,
    dry_run: bool = True,
    export_destination: str | None = None,
) -> MasterRunResult:
    runner = MasterPipelineRunner()
    return await runner.run_all(hours=hours, limit=limit, dry_run=dry_run, export_destination=export_destination)
