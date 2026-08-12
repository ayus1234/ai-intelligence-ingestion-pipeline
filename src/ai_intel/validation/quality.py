"""Data Quality Report Engine and audit validator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DataQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_id: str
    total_records: int = 0
    counts_by_vertical: dict[str, int] = Field(default_factory=dict)
    duplicate_natural_keys: int = 0
    unresolved_entities: int = 0
    freshness_violations: int = 0
    missing_github_stars: int = 0
    missing_employee_counts: int = 0
    export_row_counts: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DataQualityReporter:
    @classmethod
    def audit_run(
        self,
        run_id: str,
        records_by_type: dict[str, list[Any]],
        cutoff_hours: int = 24,
    ) -> DataQualityReport:
        """Audit ingestion pipeline run records across quality dimensions."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)
        total_records = 0
        counts_by_vertical: dict[str, int] = {}
        seen_keys: set[str] = set()
        duplicates = 0
        unresolved = 0
        freshness_violations = 0
        missing_stars = 0
        missing_employees = 0

        for vertical, records in records_by_type.items():
            counts_by_vertical[vertical] = len(records)
            total_records += len(records)

            for rec in records:
                # Natural key duplicate check
                nat_key = rec.natural_key() if hasattr(rec, "natural_key") else str(rec)
                if nat_key in seen_keys:
                    duplicates += 1
                else:
                    seen_keys.add(nat_key)

                # Entity mapping log audit
                mapping = getattr(rec, "_mapping_log", None)
                if mapping is not None and getattr(mapping, "resolution_tier", None) == "unresolved":
                    unresolved += 1

                content = getattr(rec, "content", rec)

                # Freshness audit for news & jobs
                posted_dt = getattr(content, "posted_date", getattr(content, "publication_date", None))
                if posted_dt is not None and posted_dt < cutoff_time:
                    freshness_violations += 1

                # Missing GitHub stars audit for research papers
                if hasattr(content, "github_stars"):
                    if getattr(content, "github_stars", None) is None:
                        missing_stars += 1

                # Missing employee counts audit for startups
                if hasattr(content, "data"):
                    if getattr(content.data, "employee_count", None) is None:
                        missing_employees += 1

        return DataQualityReport(
            run_id=run_id,
            total_records=total_records,
            counts_by_vertical=counts_by_vertical,
            duplicate_natural_keys=duplicates,
            unresolved_entities=unresolved,
            freshness_violations=freshness_violations,
            missing_github_stars=missing_stars,
            missing_employee_counts=missing_employees,
            generated_at=datetime.now(timezone.utc),
        )
