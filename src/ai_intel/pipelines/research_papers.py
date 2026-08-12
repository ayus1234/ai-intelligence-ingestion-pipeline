"""Research paper ingestion pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai_intel.config import Settings
from ai_intel.crawlers.research import ArxivCrawler, PapersWithCodeCrawler
from ai_intel.github import GitHubMetricsClient
from ai_intel.logging import get_logger
from ai_intel.schemas import (
    ArxivPaper,
    PaperCodeMapping,
    RepositorySource,
    ResearchIngestionResult,
    ResearchPaperRecord,
)
from ai_intel.schemas.base import SourceRef
from ai_intel.schemas.research import GitHubRepoMetrics, PaperCodeRepository
from ai_intel.storage.base import StorageRepository
from ai_intel.utils.arxiv import extract_arxiv_id, normalize_title_for_join
from ai_intel.utils.github import normalize_github_repo_url
from ai_intel.validation import RecordValidationError, RecordValidator

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class JoinedResearchPaper:
    arxiv_paper: ArxivPaper
    mapping: PaperCodeMapping | None
    repositories: tuple[PaperCodeRepository, ...]


class ResearchPaperJoiner:
    def join(
        self,
        arxiv_papers: dict[str, ArxivPaper],
        pwc_mappings: dict[str, PaperCodeMapping],
        limit: int,
    ) -> list[JoinedResearchPaper]:
        by_title = {
            normalize_title_for_join(mapping.paper_title): mapping
            for mapping in pwc_mappings.values()
            if mapping.paper_title
        }
        joined: list[JoinedResearchPaper] = []
        seen: set[str] = set()
        for arxiv_id, paper in arxiv_papers.items():
            key = extract_arxiv_id(arxiv_id) or arxiv_id
            if key in seen:
                continue
            mapping = pwc_mappings.get(key) or by_title.get(normalize_title_for_join(paper.title))
            repositories = tuple(self._rank_repositories(mapping.repositories if mapping else []))
            joined.append(JoinedResearchPaper(paper, mapping, repositories))
            seen.add(key)
            if len(joined) >= limit:
                break
        return joined

    @staticmethod
    def _rank_repositories(repositories: list[PaperCodeRepository]) -> list[PaperCodeRepository]:
        deduped: dict[str, PaperCodeRepository] = {}
        for repository in repositories:
            normalized = normalize_github_repo_url(str(repository.repo_url))
            if normalized is None:
                continue
            deduped.setdefault(normalized.html_url.lower(), repository)
        return sorted(
            deduped.values(),
            key=lambda repo: (
                bool(repo.is_official),
                bool(repo.mentioned_in_paper),
                bool(repo.mentioned_in_github),
            ),
            reverse=True,
        )


class ResearchPaperPipeline:
    def __init__(
        self,
        settings: Settings,
        storage: StorageRepository,
        arxiv_crawler: ArxivCrawler | None = None,
        pwc_crawler: PapersWithCodeCrawler | None = None,
        github_client: GitHubMetricsClient | None = None,
        validator: RecordValidator | None = None,
        joiner: ResearchPaperJoiner | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.arxiv_crawler = arxiv_crawler or ArxivCrawler(settings)
        self.pwc_crawler = pwc_crawler or PapersWithCodeCrawler(settings)
        self.github_client = github_client or GitHubMetricsClient(settings)
        self.validator = validator or RecordValidator()
        self.joiner = joiner or ResearchPaperJoiner()

    async def ingest(
        self,
        limit: int,
        run_id: str | None = None,
        session: Any | None = None,
        since: datetime | None = None,
    ) -> ResearchIngestionResult:
        run_id = run_id or f"papers-{uuid4()}"
        source_counts: dict[str, int] = {}
        success_counts: dict[str, int] = {}
        failure_counts: dict[str, int] = {}
        await self.storage.start_pipeline_run(run_id, source_counts=source_counts)

        owns_session = session is None
        if session is None:
            try:
                import aiohttp  # type: ignore[import-not-found,import-untyped,unused-ignore]
            except ImportError:
                aiohttp = None  # type: ignore[assignment]

            if aiohttp is None:
                raise RuntimeError("aiohttp is required for HTTP fetching. Install it with pip install aiohttp.")

            timeout = aiohttp.ClientTimeout(total=self.settings.default_http_timeout_seconds)
            session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.settings.crawl_user_agent},
            )

        stored = 0
        github_metrics_refreshed = 0
        failures = 0
        try:
            mappings = await self.pwc_crawler.fetch_mappings(
                session=session,
                limit=max(limit * 5, limit),
            )
            source_counts["papers_with_code_mappings"] = len(mappings)

            try:
                arxiv_ids = [key for key, mapping in mappings.items() if mapping.paper_arxiv_id]
                arxiv_papers = await self.arxiv_crawler.fetch_by_ids(arxiv_ids[: max(limit * 2, limit)], session=session)
                if len(arxiv_papers) < limit:
                    direct_papers = await self.arxiv_crawler.fetch_papers(limit=limit, session=session)
                    for p in direct_papers:
                        if p.arxiv_id not in arxiv_papers:
                            arxiv_papers[p.arxiv_id] = p
            except Exception as exc:
                logger.warning("arxiv_fetch_failed_graceful_fallback", extra={"error": str(exc)})
                arxiv_papers = {}
            if since is not None:
                if since.tzinfo is None or since.utcoffset() is None:
                    since = since.replace(tzinfo=timezone.utc)
                since = since.astimezone(timezone.utc)
                arxiv_papers = {
                    arxiv_id: paper
                    for arxiv_id, paper in arxiv_papers.items()
                    if paper.published_date >= since
                }
            source_counts["arxiv_papers"] = len(arxiv_papers)

            joined = self.joiner.join(arxiv_papers, mappings, limit=limit)
            for item in joined:
                try:
                    metrics_by_repo = await self._refresh_repository_metrics(session, item.repositories)
                    for metrics in metrics_by_repo.values():
                        await self.storage.upsert_github_metrics(metrics)
                        github_metrics_refreshed += 1
                    primary_metrics = self._choose_primary_metrics(item.repositories, metrics_by_repo)
                    record = self._build_record(item, primary_metrics)
                    self.validator.validate(record)
                    is_new = await self.storage.upsert_research_paper(record)
                    if is_new:
                        stored += 1
                except Exception as exc:
                    failures += 1
                    logger.warning(
                        "research_paper_ingest_failed",
                        extra={
                            "run_id": run_id,
                            "arxiv_id": item.arxiv_paper.arxiv_id,
                            "error": str(exc),
                        },
                    )

            success_counts = {
                "research_papers": stored,
                "github_metrics": github_metrics_refreshed,
            }
            failure_counts = {"research_papers": failures}
            await self.storage.complete_pipeline_run(
                run_id,
                success_counts=success_counts,
                failure_counts=failure_counts,
                source_counts=source_counts,
            )
            return ResearchIngestionResult(
                requested_limit=limit,
                fetched_papers=len(arxiv_papers),
                joined_papers=len(joined),
                stored_papers=stored,
                github_metrics_refreshed=github_metrics_refreshed,
                failures=failures,
            )
        finally:
            if owns_session:
                await session.close()

    async def _refresh_repository_metrics(
        self,
        session: Any,
        repositories: tuple[PaperCodeRepository, ...],
    ) -> dict[str, GitHubRepoMetrics]:
        semaphore = asyncio.Semaphore(min(4, max(1, self.settings.max_concurrent_requests)))

        async def fetch(repository: PaperCodeRepository) -> GitHubRepoMetrics | None:
            async with semaphore:
                try:
                    return await self.github_client.fetch_metrics(session, str(repository.repo_url))
                except Exception as exc:
                    logger.warning(
                        "github_metrics_refresh_failed",
                        extra={"repo_url": str(repository.repo_url), "error": str(exc)},
                    )
                    return None

        results = await asyncio.gather(*(fetch(repository) for repository in repositories))
        return {str(metrics.github_url).lower(): metrics for metrics in results if metrics is not None}

    @staticmethod
    def _choose_primary_metrics(
        repositories: tuple[PaperCodeRepository, ...],
        metrics_by_repo: dict[str, GitHubRepoMetrics],
    ) -> GitHubRepoMetrics | None:
        if not repositories:
            return None
        official_metrics = [
            metrics_by_repo.get(str(repository.repo_url).lower())
            for repository in repositories
            if repository.is_official
        ]
        official_metrics = [metrics for metrics in official_metrics if metrics is not None]
        if official_metrics:
            return max(official_metrics, key=lambda metrics: metrics.stars)
        if metrics_by_repo:
            return max(metrics_by_repo.values(), key=lambda metrics: metrics.stars)
        return None

    @staticmethod
    def _build_record(
        joined: JoinedResearchPaper,
        metrics: GitHubRepoMetrics | None,
    ) -> ResearchPaperRecord:
        paper = joined.arxiv_paper
        repo_urls = [repository.repo_url for repository in joined.repositories]
        primary_repo = metrics.github_url if metrics is not None else (repo_urls[0] if repo_urls else None)
        now = datetime.now(timezone.utc)
        repository_source = RepositorySource.PAPERS_WITH_CODE if joined.mapping else RepositorySource.NONE
        return ResearchPaperRecord(
            source=SourceRef(name="arXiv", url=paper.paper_url),
            collectedAt=now,
            content={
                "arxiv_id": paper.arxiv_id,
                "papers_with_code_id": joined.mapping.papers_with_code_id if joined.mapping else None,
                "title": paper.title,
                "authors": paper.authors,
                "paper_url": paper.paper_url,
                "primary_github_url": primary_repo,
                "github_url": primary_repo,
                "github_repositories": repo_urls,
                "github_stars": metrics.stars if metrics else None,
                "github_stars_fetched_at": metrics.fetched_at if metrics else None,
                "source_collected_at": now,
                "github_metrics_collected_at": metrics.fetched_at if metrics else None,
                "repository_source": repository_source,
                "published_date": paper.published_date,
            },
        )


async def run_research_paper_ingestion(
    settings: Settings,
    storage: StorageRepository,
    limit: int,
    since: datetime | None = None,
) -> ResearchIngestionResult:
    pipeline = ResearchPaperPipeline(settings=settings, storage=storage)
    return await pipeline.ingest(limit=limit, since=since)
