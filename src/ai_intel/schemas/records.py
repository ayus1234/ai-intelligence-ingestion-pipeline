"""Canonical entity schemas for final records."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, NonNegativeInt, field_validator

from ai_intel.schemas.base import RecordEnvelope, RecordType, SourceRef


class PricingModel(StrEnum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class RepositorySource(StrEnum):
    PAPERS_WITH_CODE = "PAPERS_WITH_CODE"
    MANUAL = "MANUAL"
    GITHUB_SEARCH = "GITHUB_SEARCH"
    NONE = "NONE"


class StartupData(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    employee_count: NonNegativeInt | None = Field(default=None, alias="employeeCount")
    employee_count_raw: str | None = Field(default=None, alias="employeeCountRaw")
    website_url: AnyUrl | None = Field(default=None, alias="websiteUrl")
    company_domain: str | None = Field(default=None, alias="companyDomain")
    batch: str | None = None
    industry: str | None = None
    source_collected_at: datetime | None = Field(default=None, alias="sourceCollectedAt")

    @field_validator("source_collected_at")
    @classmethod
    def source_collected_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source_collected_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class StartupContent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    entity_name: str = Field(alias="entityName", min_length=1)
    raw_entity_name: str | None = Field(default=None, alias="rawEntityName")
    data: StartupData = Field(default_factory=StartupData)


class ProductContent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    product_name: str = Field(alias="productName", min_length=1)
    startup_name: str = Field(alias="startupName", min_length=1)
    raw_startup_name: str | None = Field(default=None, alias="rawStartupName")
    pricing_model: PricingModel = Field(alias="pricingModel")
    category: str | None = Field(default=None)
    source_url: AnyUrl = Field(alias="sourceUrl")


class ResearchPaperContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arxiv_id: str | None = None
    papers_with_code_id: str | None = None
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    paper_url: AnyUrl
    primary_github_url: AnyUrl | None = None
    github_url: AnyUrl | None = None
    github_repositories: list[AnyUrl] = Field(default_factory=list)
    github_stars: NonNegativeInt | None = None
    github_stars_fetched_at: datetime | None = None
    source_collected_at: datetime | None = None
    github_metrics_collected_at: datetime | None = None
    repository_source: RepositorySource = RepositorySource.NONE
    published_date: datetime

    @field_validator("published_date")
    @classmethod
    def published_date_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("published_date must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("github_stars_fetched_at")
    @classmethod
    def stars_timestamp_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("github_stars_fetched_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("source_collected_at", "github_metrics_collected_at")
    @classmethod
    def lineage_timestamps_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("lineage timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)


class JobContent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    company: str = Field(min_length=1)
    raw_company: str = Field(alias="rawCompany", min_length=1)
    company_domain: str | None = Field(default=None, alias="companyDomain")
    role_title: str = Field(alias="roleTitle", min_length=1)
    normalized_role: str = Field(alias="normalizedRole", min_length=1)
    role_family: str = Field(alias="roleFamily", min_length=1)
    location: str | None = None
    is_remote: bool = Field(default=False, alias="isRemote")
    employment_type: str | None = Field(default=None, alias="employmentType")
    salary_text: str | None = Field(default=None, alias="salaryText")
    description: str = Field(default="", min_length=0)
    posted_date: datetime = Field(alias="postedDate")
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="firstSeenAt")
    source_job_id: str | None = Field(default=None, alias="sourceJobId")
    source_name: str = Field(alias="sourceName", min_length=1)
    source_url: AnyUrl = Field(alias="sourceUrl")

    @property
    def date(self) -> datetime:
        return self.posted_date

    @field_validator("posted_date", "first_seen_at")
    @classmethod
    def job_timestamps_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("job timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)


class NewsContent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    publication_date: datetime = Field(alias="publicationDate")
    source_name: str = Field(alias="sourceName", min_length=1)
    source_url: AnyUrl = Field(alias="sourceUrl")
    date_source: str = Field(alias="dateSource", min_length=1)
    freshness_verified: bool = Field(default=False, alias="freshnessVerified")
    content_hash: str = Field(alias="contentHash", min_length=1)

    @field_validator("publication_date")
    @classmethod
    def publication_date_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("publication_date must be timezone-aware")
        return value.astimezone(timezone.utc)


class StartupRecord(RecordEnvelope[StartupContent]):
    record_type: RecordType = Field(default=RecordType.STARTUP, alias="recordType")
    source: SourceRef | None = None
    content: StartupContent

    def natural_key(self) -> str:
        if self.content.data.company_domain:
            domain = self.content.data.company_domain.lower().strip()
            if domain.startswith("www."):
                domain = domain[4:]
            if domain:
                return f"startup:domain:{domain}"
        if self.source and self.source.url:
            url_str = str(self.source.url).lower()
            if "/companies/" in url_str:
                slug = url_str.split("/companies/")[-1].strip("/")
                if slug:
                    return f"startup:yc:{slug}"
            return f"startup:url:{url_str}"
        return f"startup:name:{self.content.entity_name.lower().strip()}"


class ProductRecord(RecordEnvelope[ProductContent]):
    record_type: RecordType = Field(default=RecordType.PRODUCT, alias="recordType")
    source: SourceRef | None = None
    content: ProductContent

    def natural_key(self) -> str:
        if self.content.source_url:
            return f"product:url:{str(self.content.source_url).lower()}"
        return f"product:name:{self.content.product_name.lower().strip()}"


class ResearchPaperRecord(RecordEnvelope[ResearchPaperContent]):
    record_type: RecordType = Field(default=RecordType.RESEARCH_PAPER, alias="recordType")
    source: SourceRef | None = None
    content: ResearchPaperContent


class JobRecord(RecordEnvelope[JobContent]):
    record_type: RecordType = Field(default=RecordType.JOB, alias="recordType")
    source: SourceRef | None = None
    content: JobContent

    def natural_key(self) -> str:
        domain = (self.content.company_domain or "").lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        norm_role = self.content.normalized_role.lower().strip()
        comp = self.content.company.lower().strip()

        if domain and norm_role:
            return f"job:company:{domain}:role:{norm_role}"
        if comp and norm_role:
            return f"job:company:{comp}:role:{norm_role}"
        if self.content.source_job_id:
            src = self.content.source_name.lower().strip()
            jid = self.content.source_job_id.lower().strip()
            return f"job:source:{src}:id:{jid}"
        return f"job:url:{str(self.content.source_url).lower()}"


class NewsRecord(RecordEnvelope[NewsContent]):
    record_type: RecordType = Field(default=RecordType.NEWS, alias="recordType")
    source: SourceRef | None = None
    content: NewsContent

    def natural_key(self) -> str:
        if self.content.content_hash:
            return f"news:hash:{self.content.content_hash}"
        return f"news:url:{str(self.content.source_url).lower()}"


class EntityMappingLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_name: str
    canonical_name: str | None
    canonical_id: str | None = None
    entity_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    method: str
    resolution_tier: str = "unresolved"
    signals_evaluated: list[str] = Field(default_factory=list)
    source_url: AnyUrl | None = None
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("resolved_at")
    @classmethod
    def resolved_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("resolved_at must be timezone-aware")
        return value.astimezone(timezone.utc)
