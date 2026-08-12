"""Product ingestion schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator

from ai_intel.schemas.records import PricingModel


class ProductCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1)
    raw_startup_name: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: AnyUrl
    pricing_model: PricingModel = PricingModel.FREEMIUM
    category: str | None = None
    source_collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("source_collected_at")
    @classmethod
    def collected_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source_collected_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class ProductIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_limit: int
    fetched_products: int
    stored_products: int
    resolved_startups: int
    failures: int
