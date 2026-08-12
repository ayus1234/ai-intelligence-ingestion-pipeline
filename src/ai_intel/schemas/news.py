"""News ingestion schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class NewsCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: AnyUrl
    published_date: datetime | None = None
    date_source: str = "rss"
    summary: str | None = None
    raw_html: str | None = None
    source_collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("published_date", "source_collected_at")
    @classmethod
    def date_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)


class NewsIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_limit: int
    cutoff_hours: int
    fetched_candidates: int
    verified_articles: int
    stored_articles: int
    rejected_stale: int
    failures: int
