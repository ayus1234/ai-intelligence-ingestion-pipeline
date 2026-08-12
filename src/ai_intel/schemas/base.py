"""Shared Pydantic models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class RecordType(StrEnum):
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    url: AnyUrl


ContentT = TypeVar("ContentT", bound=BaseModel)


class RecordEnvelope(BaseModel, Generic[ContentT]):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(default="1.0", alias="schemaVersion")
    record_type: RecordType = Field(alias="recordType")
    source: SourceRef | None = None
    content: ContentT
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="collectedAt")

    @field_validator("collected_at")
    @classmethod
    def collected_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collected_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    def natural_key(self) -> str:
        content = self.content.model_dump(mode="json")
        candidates = (
            content.get("arxiv_id"),
            content.get("paper_url"),
            content.get("source_url"),
            content.get("url"),
            content.get("title"),
            content.get("entity_name"),
            content.get("startup_name"),
            content.get("company"),
        )
        for candidate in candidates:
            if candidate:
                return f"{self.record_type}:{candidate}".lower()
        return f"{self.record_type}:{self.model_dump_json()}"


class ErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
