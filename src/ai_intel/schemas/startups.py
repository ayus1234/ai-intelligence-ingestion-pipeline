"""Startup ingestion schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, NonNegativeInt, field_validator


class StartupCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_name: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: AnyUrl
    website_url: AnyUrl | None = None
    company_domain: str | None = None
    employee_count: NonNegativeInt | None = None
    employee_count_raw: str | None = None
    batch: str | None = None
    industry: str | None = None
    source_payload: dict[str, object] = Field(default_factory=dict)
    source_collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("source_collected_at")
    @classmethod
    def collected_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source_collected_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class StartupEnrichment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_name: str
    source_name: str
    source_url: AnyUrl
    employee_count: NonNegativeInt | None = None
    employee_count_raw: str | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("collected_at")
    @classmethod
    def collected_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class StartupIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_limit: int
    fetched_startups: int
    enriched_startups: int
    stored_startups: int
    unresolved_mappings: int
    failures: int
