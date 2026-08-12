"""Canonical record validation before persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ai_intel.schemas import RecordEnvelope, RecordType, ResearchPaperRecord, StartupRecord


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    message: str


class RecordValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        joined = "; ".join(f"{issue.field}: {issue.message}" for issue in issues)
        super().__init__(joined)


class RecordValidator:
    def __init__(self, schema_version: str = "1.0") -> None:
        self.schema_version = schema_version

    def validate(self, record: RecordEnvelope, existing_natural_keys: set[str] | None = None) -> None:
        issues: list[ValidationIssue] = []
        if record.schema_version != self.schema_version:
            issues.append(ValidationIssue("schemaVersion", "unsupported schema version"))
        if existing_natural_keys and record.natural_key() in existing_natural_keys:
            issues.append(ValidationIssue("natural_key", "duplicate natural key"))
        if record.collected_at > datetime.now(timezone.utc):
            issues.append(ValidationIssue("collectedAt", "collection timestamp is in the future"))
        if record.record_type is RecordType.RESEARCH_PAPER:
            issues.extend(self._validate_research_paper(record))
        if record.record_type is RecordType.STARTUP:
            issues.extend(self._validate_startup(record))
        if issues:
            raise RecordValidationError(issues)

    @staticmethod
    def _validate_research_paper(record: ResearchPaperRecord) -> list[ValidationIssue]:
        content = record.content
        issues: list[ValidationIssue] = []
        if not content.title.strip():
            issues.append(ValidationIssue("content.title", "title is required"))
        if not content.paper_url:
            issues.append(ValidationIssue("content.paper_url", "paper URL is required"))
        if content.published_date > datetime.now(timezone.utc):
            issues.append(ValidationIssue("content.published_date", "publication date is in the future"))
        if content.github_stars is not None and content.github_url is None:
            issues.append(ValidationIssue("content.github_stars", "stars require a GitHub URL"))
        if content.github_stars is not None and content.github_stars_fetched_at is None:
            issues.append(
                ValidationIssue("content.github_stars_fetched_at", "star refresh timestamp is required")
            )
        return issues

    @staticmethod
    def _validate_startup(record: StartupRecord) -> list[ValidationIssue]:
        content = record.content
        issues: list[ValidationIssue] = []
        if not content.entity_name.strip():
            issues.append(ValidationIssue("content.entityName", "canonical startup name is required"))
        if content.data.employee_count is not None and content.data.employee_count < 0:
            issues.append(ValidationIssue("content.data.employeeCount", "employee count cannot be negative"))
        if content.data.source_collected_at and content.data.source_collected_at > datetime.now(timezone.utc):
            issues.append(ValidationIssue("content.data.sourceCollectedAt", "source timestamp is in the future"))
        return issues
