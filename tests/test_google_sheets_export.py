"""Tests for GoogleSheetsExporter and 6-tab manifest generation."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from ai_intel.exporters.sheets import GoogleSheetsExporter
from ai_intel.schemas import JobRecord, NewsRecord, ProductRecord, ResearchPaperRecord, StartupRecord


@pytest.mark.asyncio
async def test_google_sheets_exporter_6_tabs() -> None:
    now_dt = datetime.now(timezone.utc)
    s1 = StartupRecord(content={"entityName": "OpenAI", "rawEntityName": "OpenAI Inc.", "data": {"companyDomain": "openai.com"}})
    p1 = ProductRecord(content={"productName": "ChatGPT", "startupName": "OpenAI", "pricingModel": "FREEMIUM", "sourceUrl": "https://chatgpt.com"})
    r1 = ResearchPaperRecord(content={"title": "Attention Paper", "authors": ["Author A"], "paper_url": "https://arxiv.org/abs/1706.03762", "published_date": now_dt})
    n1 = NewsRecord(content={"title": "AI Model News", "content": "News body", "publicationDate": now_dt, "sourceName": "TC", "sourceUrl": "https://tc.com/1", "dateSource": "meta", "freshnessVerified": True, "contentHash": "h1"})
    j1 = JobRecord(content={"company": "OpenAI", "rawCompany": "OpenAI", "roleTitle": "Senior ML Engineer", "normalizedRole": "senior ml engineer", "roleFamily": "ML Engineer", "isRemote": True, "postedDate": now_dt, "firstSeenAt": now_dt, "sourceName": "AIJobs", "sourceUrl": "https://aijobs.com/1"})

    records_by_type = {
        "startups": [s1],
        "products": [p1],
        "papers": [r1],
        "news": [n1],
        "jobs": [j1],
    }

    exporter = GoogleSheetsExporter()
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = await exporter.export(
            run_id="test-run-123",
            destination=tmp_dir,
            records_by_type=records_by_type,
            quality_report={"quality_score": 1.0},
        )

        assert res.status == "SUCCESS"
        assert res.row_counts["Startups"] == 1
        assert res.row_counts["Products"] == 1
        assert res.row_counts["Research Papers"] == 1
        assert res.row_counts["AI News"] == 1
        assert res.row_counts["AI Jobs"] == 1
        assert res.row_counts["Entity Mapping Log"] >= 0
        assert res.row_counts["Pipeline Run Manifest"] == 1

        # Check all CSV files & manifest created
        assert os.path.exists(os.path.join(tmp_dir, "01_startups.csv"))
        assert os.path.exists(os.path.join(tmp_dir, "02_products.csv"))
        assert os.path.exists(os.path.join(tmp_dir, "03_research_papers.csv"))
        assert os.path.exists(os.path.join(tmp_dir, "04_ai_news.csv"))
        assert os.path.exists(os.path.join(tmp_dir, "05_ai_jobs.csv"))
        assert os.path.exists(os.path.join(tmp_dir, "06_entity_mapping_log.csv"))

        manifest_path = os.path.join(tmp_dir, "07_pipeline_manifest.json")
        assert os.path.exists(manifest_path)
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            assert manifest["run_id"] == "test-run-123"
            assert manifest["row_counts"]["Startups"] == 1
