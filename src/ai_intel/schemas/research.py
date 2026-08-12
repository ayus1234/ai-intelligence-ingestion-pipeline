"""Research-paper-specific ingestion schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, NonNegativeInt, field_validator


class ArxivPaper(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arxiv_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    paper_url: AnyUrl
    published_date: datetime
    updated_date: datetime | None = None
    summary: str | None = None
    categories: list[str] = Field(default_factory=list)

    @field_validator("title", "summary")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())

    @field_validator("published_date", "updated_date")
    @classmethod
    def datetimes_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("research paper timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)


class PaperCodeRepository(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_url: AnyUrl
    is_official: bool | None = None
    mentioned_in_paper: bool | None = None
    mentioned_in_github: bool | None = None
    framework: str | None = None


class PaperCodeMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_url: AnyUrl | None = None
    paper_url_abs: AnyUrl | None = None
    paper_title: str | None = None
    paper_arxiv_id: str | None = None
    papers_with_code_id: str | None = None
    repositories: list[PaperCodeRepository] = Field(default_factory=list)


class GitHubRepoMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    github_url: AnyUrl
    owner: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    stars: NonNegativeInt
    forks: NonNegativeInt | None = None
    watchers: NonNegativeInt | None = None
    open_issues: NonNegativeInt | None = None
    default_branch: str | None = None
    archived: bool | None = None
    license: str | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    api_status: int = 200
    response_hash: str | None = None

    @field_validator("fetched_at")
    @classmethod
    def fetched_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class ResearchIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_limit: int
    fetched_papers: int
    joined_papers: int
    stored_papers: int
    github_metrics_refreshed: int
    failures: int
