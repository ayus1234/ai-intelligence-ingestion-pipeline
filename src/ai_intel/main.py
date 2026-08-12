"""Application entry point for orchestration commands."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone

from ai_intel.config import get_settings
from ai_intel.config.source_registry import DEFAULT_SOURCES
from ai_intel.logging import configure_logging, get_logger
from ai_intel.storage import InMemoryStorageRepository
from ai_intel.storage.postgres import PostgresStorageRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI intelligence ingestion pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check-config", help="Validate configuration loading")
    subparsers.add_parser("list-sources", help="List configured ingestion sources")

    ingest_papers = subparsers.add_parser("ingest-papers", help="Run research paper ingestion")
    ingest_papers.add_argument("--limit", type=int, default=1000, help="Number of papers to ingest")
    ingest_papers.add_argument(
        "--since",
        help="Only persist papers with publication dates on or after this ISO date/datetime",
    )
    ingest_papers.add_argument(
        "--dry-run",
        action="store_true",
        help="Use in-memory storage instead of PostgreSQL",
    )

    ingest_startups = subparsers.add_parser("ingest-startups", help="Run startup ingestion")
    ingest_startups.add_argument("--limit", type=int, default=1000, help="Number of startups to ingest")
    ingest_startups.add_argument(
        "--dry-run",
        action="store_true",
        help="Use in-memory storage instead of PostgreSQL",
    )
    ingest_startups.add_argument(
        "--no-wellfound",
        action="store_true",
        help="Disable Wellfound enrichment",
    )

    ingest_products = subparsers.add_parser("ingest-products", help="Run product ingestion")
    ingest_products.add_argument("--limit", type=int, default=1000, help="Number of products to ingest")
    ingest_products.add_argument(
        "--dry-run",
        action="store_true",
        help="Use in-memory storage instead of PostgreSQL",
    )

    ingest_news = subparsers.add_parser("ingest-news", help="Run AI news ingestion")
    ingest_news.add_argument("--hours", type=int, default=24, help="Freshness cutoff window in hours")
    ingest_news.add_argument("--limit", type=int, default=1000, help="Number of news articles to ingest")
    ingest_news.add_argument(
        "--dry-run",
        action="store_true",
        help="Use in-memory storage instead of PostgreSQL",
    )

    ingest_jobs = subparsers.add_parser("ingest-jobs", help="Run AI job ingestion")
    ingest_jobs.add_argument("--hours", type=int, default=24, help="Freshness cutoff window in hours")
    ingest_jobs.add_argument("--limit", type=int, default=1000, help="Number of jobs to ingest")
    ingest_jobs.add_argument(
        "--dry-run",
        action="store_true",
        help="Use in-memory storage instead of PostgreSQL",
    )

    extract_llm = subparsers.add_parser("extract-llm", help="Run LLM structured extraction engine")
    extract_llm.add_argument("--input", type=str, required=True, help="Input text or file path to extract")
    extract_llm.add_argument("--schema", type=str, default="startup", help="Target schema name (startup|product|paper|news|job)")
    extract_llm.add_argument("--mock", action="store_true", help="Force MockLLMProvider for offline/dry-run")
    extract_llm.add_argument("--dry-run", action="store_true", help="Perform extraction without persisting")

    subparsers.add_parser("metrics", help="Output Prometheus-compatible system observability metrics")

    run_all = subparsers.add_parser("run-all", help="Run end-to-end master pipeline across all 5 verticals")
    run_all.add_argument("--hours", type=int, default=24, help="Freshness cutoff window in hours")
    run_all.add_argument("--limit", type=int, default=1000, help="Per-crawler item ingestion limit")
    run_all.add_argument("--destination", type=str, default=None, help="Export output directory")
    run_all.add_argument(
        "--dry-run",
        action="store_true",
        help="Use in-memory storage instead of PostgreSQL",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    if args.command == "check-config":
        logger.info(
            "configuration_loaded",
            extra={
                "app_env": settings.app_env,
                "database_configured": bool(settings.database_url),
                "redis_configured": bool(settings.redis_url),
            },
        )
        return

    if args.command == "list-sources":
        for source in DEFAULT_SOURCES:
            logger.info("source_registered", extra=asdict(source))
        return

    if args.command == "ingest-papers":
        asyncio.run(_ingest_papers(limit=args.limit, dry_run=args.dry_run, since=args.since))
        return

    if args.command == "ingest-startups":
        asyncio.run(_ingest_startups(limit=args.limit, dry_run=args.dry_run, use_wellfound=not args.no_wellfound))
        return

    if args.command == "ingest-products":
        asyncio.run(_ingest_products(limit=args.limit, dry_run=args.dry_run))
        return

    if args.command == "ingest-news":
        asyncio.run(_ingest_news(hours=args.hours, limit=args.limit, dry_run=args.dry_run))
        return

    if args.command == "ingest-jobs":
        asyncio.run(_ingest_jobs(hours=args.hours, limit=args.limit, dry_run=args.dry_run))
        return

    if args.command == "extract-llm":
        asyncio.run(_extract_llm(input_text=args.input, schema_name=args.schema, mock=args.mock, dry_run=args.dry_run))
        return

    if args.command == "metrics":
        from ai_intel.metrics import metrics_collector
        print(metrics_collector.export_prometheus_text())
        return

    if args.command == "run-all":
        asyncio.run(_run_all(hours=args.hours, limit=args.limit, dry_run=args.dry_run, destination=args.destination))
        return


async def _ingest_papers(limit: int, dry_run: bool, since: str | None) -> None:
    from ai_intel.pipelines import ResearchPaperPipeline

    settings = get_settings()
    logger = get_logger(__name__)
    since_dt = _parse_since(since) if since else None
    if dry_run:
        storage = InMemoryStorageRepository()
        result = await ResearchPaperPipeline(settings=settings, storage=storage).ingest(
            limit=limit,
            since=since_dt,
        )
    else:
        async with PostgresStorageRepository(settings) as storage:
            result = await ResearchPaperPipeline(settings=settings, storage=storage).ingest(
                limit=limit,
                since=since_dt,
            )

    logger.info("research_paper_ingestion_complete", extra=result.model_dump())


async def _ingest_startups(limit: int, dry_run: bool, use_wellfound: bool) -> None:
    from ai_intel.pipelines import StartupPipeline

    settings = get_settings()
    logger = get_logger(__name__)
    if dry_run:
        storage = InMemoryStorageRepository()
        result = await StartupPipeline(settings=settings, storage=storage).ingest(
            limit=limit,
            use_wellfound=use_wellfound,
        )
    else:
        async with PostgresStorageRepository(settings) as storage:
            result = await StartupPipeline(settings=settings, storage=storage).ingest(
                limit=limit,
                use_wellfound=use_wellfound,
            )

    logger.info("startup_ingestion_complete", extra=result.model_dump())


async def _ingest_products(limit: int, dry_run: bool) -> None:
    from ai_intel.pipelines import ProductPipeline

    settings = get_settings()
    logger = get_logger(__name__)
    if dry_run:
        storage = InMemoryStorageRepository()
        result = await ProductPipeline(settings=settings, storage=storage).ingest(limit=limit)
    else:
        async with PostgresStorageRepository(settings) as storage:
            result = await ProductPipeline(settings=settings, storage=storage).ingest(limit=limit)

    logger.info("product_ingestion_complete", extra=result.model_dump())


async def _ingest_news(hours: int, limit: int, dry_run: bool) -> None:
    from ai_intel.pipelines import NewsPipeline

    settings = get_settings()
    logger = get_logger(__name__)
    if dry_run:
        storage = InMemoryStorageRepository()
        result = await NewsPipeline(settings=settings, storage=storage).ingest(hours=hours, limit=limit)
    else:
        async with PostgresStorageRepository(settings) as storage:
            result = await NewsPipeline(settings=settings, storage=storage).ingest(hours=hours, limit=limit)

    logger.info("news_ingestion_complete", extra=result.model_dump())


async def _ingest_jobs(hours: int, limit: int, dry_run: bool) -> None:
    from ai_intel.pipelines import JobPipeline

    settings = get_settings()
    logger = get_logger(__name__)
    if dry_run:
        storage = InMemoryStorageRepository()
        result = await JobPipeline(settings=settings, storage=storage).ingest(hours=hours, limit=limit)
    else:
        async with PostgresStorageRepository(settings) as storage:
            result = await JobPipeline(settings=settings, storage=storage).ingest(hours=hours, limit=limit)

    logger.info("job_ingestion_complete", extra=result.model_dump())


async def _extract_llm(input_text: str, schema_name: str, mock: bool, dry_run: bool) -> None:
    import os
    from ai_intel.llm import (
        GeminiFlashProvider,
        GroqFallbackProvider,
        GroqLlamaProvider,
        LLMOrchestrator,
        LLMProvider,
        MockLLMProvider,
    )

    settings = get_settings()
    logger = get_logger(__name__)

    # Check if input is a readable file path
    text_content = input_text
    if os.path.exists(input_text):
        with open(input_text, "r", encoding="utf-8", errors="ignore") as f:
            text_content = f.read()

    providers: list[LLMProvider] = []
    if mock:
        providers.append(MockLLMProvider())
    else:
        if getattr(settings, "gemini_api_key", None):
            providers.append(GeminiFlashProvider(api_key=settings.gemini_api_key))
        if settings.primary_groq_key:
            providers.append(GroqLlamaProvider(api_key=settings.primary_groq_key))
        if getattr(settings, "groq_api_key_2", None):
            providers.append(GroqFallbackProvider(api_key=settings.groq_api_key_2))
        providers.append(MockLLMProvider())  # Fallback

    orchestrator = LLMOrchestrator(providers=providers)
    res = await orchestrator.extract(schema_name=schema_name, text=text_content, source_url=input_text)
    logger.info("llm_extraction_complete", extra={"result": res})


async def _run_all(hours: int, limit: int, dry_run: bool, destination: str | None) -> None:
    from ai_intel.pipelines import run_master_pipeline

    logger = get_logger(__name__)
    res = await run_master_pipeline(hours=hours, limit=limit, dry_run=dry_run, export_destination=destination)
    logger.info("master_run_all_complete", extra={
        "run_id": res.run_id,
        "total_records": res.total_records,
        "vertical_counts": res.vertical_counts,
        "export_destination": res.export_destination,
    })


def _parse_since(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    main()
