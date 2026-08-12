"""Canonical schema exports."""

from ai_intel.schemas.base import RecordEnvelope, RecordType, SourceRef
from ai_intel.schemas.crawl import CrawlTarget, FetchResult, RawCandidate, RawDocument
from ai_intel.schemas.records import (
    EntityMappingLog,
    JobRecord,
    NewsRecord,
    PricingModel,
    ProductRecord,
    RepositorySource,
    ResearchPaperRecord,
    StartupRecord,
)
from ai_intel.schemas.research import (
    ArxivPaper,
    GitHubRepoMetrics,
    PaperCodeMapping,
    PaperCodeRepository,
    ResearchIngestionResult,
)
from ai_intel.schemas.jobs import JobCandidate, JobIngestionResult
from ai_intel.schemas.news import NewsCandidate, NewsIngestionResult
from ai_intel.schemas.products import ProductCandidate, ProductIngestionResult
from ai_intel.schemas.startups import StartupCandidate, StartupEnrichment, StartupIngestionResult

__all__ = [
    "CrawlTarget",
    "EntityMappingLog",
    "FetchResult",
    "JobCandidate",
    "JobIngestionResult",
    "JobRecord",
    "NewsCandidate",
    "NewsIngestionResult",
    "NewsRecord",
    "PricingModel",
    "ProductCandidate",
    "ProductIngestionResult",
    "ProductRecord",
    "RawCandidate",
    "RawDocument",
    "RecordEnvelope",
    "RecordType",
    "RepositorySource",
    "ResearchPaperRecord",
    "ArxivPaper",
    "GitHubRepoMetrics",
    "PaperCodeMapping",
    "PaperCodeRepository",
    "ResearchIngestionResult",
    "SourceRef",
    "StartupRecord",
    "StartupCandidate",
    "StartupEnrichment",
    "StartupIngestionResult",
]
