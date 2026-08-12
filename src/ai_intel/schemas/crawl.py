"""Schemas for crawl targets and raw documents."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, NonNegativeInt, field_validator

from ai_intel.schemas.base import RecordType


class CrawlStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    FETCHED = "fetched"
    PARSED = "parsed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CrawlTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: AnyUrl
    source_name: str = Field(min_length=1)
    source_kind: str
    priority: int = 100
    metadata: dict[str, Any] = Field(default_factory=dict)


class FetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: CrawlTarget
    status_code: int
    final_url: AnyUrl
    headers: dict[str, str] = Field(default_factory=dict)
    body: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rendered_with_playwright: bool = False

    @field_validator("fetched_at")
    @classmethod
    def fetched_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class RawDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_url: AnyUrl
    fetched_at: datetime
    http_status: int
    headers: dict[str, str] = Field(default_factory=dict)
    raw_html: str | None = None
    cleaned_text: str | None = None
    content_hash: str


class RawCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_type: RecordType
    source_name: str
    source_url: AnyUrl
    raw_text: str
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence: dict[str, Any] = Field(default_factory=dict)
    token_estimate: NonNegativeInt | None = None

