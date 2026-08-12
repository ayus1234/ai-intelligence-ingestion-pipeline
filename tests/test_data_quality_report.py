"""Tests for DataQualityReporter and audit validation."""

from datetime import datetime, timezone

from ai_intel.schemas import EntityMappingLog, StartupRecord
from ai_intel.validation.quality import DataQualityReporter


def test_data_quality_reporter_audit() -> None:
    now_dt = datetime.now(timezone.utc)
    s1 = StartupRecord(content={"entityName": "OpenAI", "rawEntityName": "OpenAI Inc.", "data": {}})
    mapping1 = EntityMappingLog(raw_name="OpenAI Inc.", canonical_name="OpenAI", entity_type="startup", confidence=1.0, method="alias", resolution_tier="alias")
    s1.__dict__["_mapping_log"] = mapping1

    s2 = StartupRecord(content={"entityName": "Anon AI", "rawEntityName": "Anon AI Inc.", "data": {}})
    mapping2 = EntityMappingLog(raw_name="Anon AI Inc.", canonical_name=None, entity_type="startup", confidence=0.0, method="unresolved", resolution_tier="unresolved")
    s2.__dict__["_mapping_log"] = mapping2

    records_by_type = {
        "startups": [s1, s2],
    }

    report = DataQualityReporter.audit_run(run_id="run-audit-1", records_by_type=records_by_type)

    assert report.run_id == "run-audit-1"
    assert report.total_records == 2
    assert report.counts_by_vertical["startups"] == 2
    assert report.unresolved_entities == 1
    assert report.missing_employee_counts == 2
