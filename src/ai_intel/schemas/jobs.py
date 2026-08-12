"""Job ingestion schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class JobCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_title: str = Field(min_length=1)
    raw_company_name: str = Field(min_length=1)
    company_domain: str | None = None
    source_name: str = Field(min_length=1)
    source_url: AnyUrl
    location: str | None = None
    is_remote: bool = False
    employment_type: str | None = None
    salary_text: str | None = None
    description: str = ""
    posted_date: datetime | None = None
    source_job_id: str | None = None
    source_collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("posted_date", "source_collected_at")
    @classmethod
    def date_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)


class JobIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_limit: int
    cutoff_hours: int
    fetched_jobs: int
    stored_jobs: int
    resolved_companies: int
    rejected_stale: int
    failures: int
