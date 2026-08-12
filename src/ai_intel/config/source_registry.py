"""Static source registry used by initial crawler planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceKind(StrEnum):
    STARTUP = "startup"
    PRODUCT = "product"
    RESEARCH = "research"
    NEWS = "news"
    JOB = "job"


class FetchMode(StrEnum):
    HTTP = "http"
    PLAYWRIGHT = "playwright"
    API = "api"
    FEED = "feed"


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    max_concurrency: int = 4
    requests_per_minute: int = 30
    requires_freshness: bool = False
    requires_playwright_fallback: bool = False


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    name: str
    kind: SourceKind
    base_url: str
    fetch_mode: FetchMode
    policy: SourcePolicy = field(default_factory=SourcePolicy)


DEFAULT_SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition("arXiv", SourceKind.RESEARCH, "https://export.arxiv.org/api/query", FetchMode.API),
    SourceDefinition(
        "Papers With Code Data",
        SourceKind.RESEARCH,
        "https://github.com/paperswithcode/paperswithcode-data",
        FetchMode.API,
    ),
    SourceDefinition("Y Combinator", SourceKind.STARTUP, "https://www.ycombinator.com/companies", FetchMode.HTTP),
    SourceDefinition("Wellfound", SourceKind.STARTUP, "https://wellfound.com/jobs", FetchMode.PLAYWRIGHT),
    SourceDefinition("YCDB", SourceKind.STARTUP, "https://www.ycdb.co/", FetchMode.HTTP),
    SourceDefinition("TopAI.tools", SourceKind.PRODUCT, "https://topai.tools/browse", FetchMode.HTTP),
    SourceDefinition("Futurepedia", SourceKind.PRODUCT, "https://www.futurepedia.io/", FetchMode.HTTP),
    SourceDefinition("AI Valley", SourceKind.PRODUCT, "https://aivalley.ai/", FetchMode.HTTP),
    SourceDefinition("AIxploria", SourceKind.PRODUCT, "https://www.aixploria.com/en/categories-ai/", FetchMode.HTTP),
    SourceDefinition(
        "TechCrunch AI",
        SourceKind.NEWS,
        "https://techcrunch.com/category/artificial-intelligence/",
        FetchMode.HTTP,
        SourcePolicy(requires_freshness=True),
    ),
    SourceDefinition(
        "The Verge AI",
        SourceKind.NEWS,
        "https://www.theverge.com/ai-artificial-intelligence",
        FetchMode.HTTP,
        SourcePolicy(requires_freshness=True),
    ),
    SourceDefinition(
        "MarkTechPost AI",
        SourceKind.NEWS,
        "https://www.marktechpost.com/category/technology/artificial-intelligence/",
        FetchMode.HTTP,
        SourcePolicy(requires_freshness=True),
    ),
    SourceDefinition(
        "The Decoder AI",
        SourceKind.NEWS,
        "https://the-decoder.com/artificial-intelligence-news/",
        FetchMode.HTTP,
        SourcePolicy(requires_freshness=True),
    ),
    SourceDefinition(
        "MIT News AI",
        SourceKind.NEWS,
        "https://news.mit.edu/topic/artificial-intelligence2?type=2",
        FetchMode.HTTP,
        SourcePolicy(requires_freshness=True),
    ),
    SourceDefinition(
        "AIJobs.com",
        SourceKind.JOB,
        "https://www.aijobs.com/jobs",
        FetchMode.HTTP,
        SourcePolicy(requires_freshness=True),
    ),
    SourceDefinition(
        "Machine Learning Jobs",
        SourceKind.JOB,
        "https://machinelearningjobs.co.uk/jobs.json",
        FetchMode.FEED,
        SourcePolicy(requires_freshness=True, requests_per_minute=1),
    ),
    SourceDefinition(
        "Jobicy",
        SourceKind.JOB,
        "https://jobicy.com/api/v2/remote-jobs?count=100&tag=ai",
        FetchMode.API,
        SourcePolicy(requires_freshness=True, requests_per_minute=30),
    ),
    SourceDefinition(
        "RemoteOK",
        SourceKind.JOB,
        "https://remoteok.com/api?tags=machine-learning,ai",
        FetchMode.API,
        SourcePolicy(requires_freshness=True, requests_per_minute=30),
    ),
    SourceDefinition(
        "Wellfound Jobs",
        SourceKind.JOB,
        "https://wellfound.com/jobs",
        FetchMode.PLAYWRIGHT,
        SourcePolicy(requires_freshness=True, requires_playwright_fallback=True),
    ),
)

