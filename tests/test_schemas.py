from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_intel.schemas import (
    JobRecord,
    NewsRecord,
    PricingModel,
    ProductRecord,
    ResearchPaperRecord,
    SourceRef,
    StartupRecord,
)


def test_startup_record_accepts_required_submission_shape() -> None:
    record = StartupRecord(
        source=SourceRef(name="YC", url="https://www.ycombinator.com/companies/acme"),
        content={"entityName": "OpenAI", "data": {"employeeCount": 1000}},
    )

    dumped = record.model_dump(by_alias=True)
    assert dumped["recordType"] == "STARTUP"
    assert dumped["schemaVersion"] == "1.0"
    assert dumped["content"]["entityName"] == "OpenAI"


def test_product_pricing_model_is_restricted() -> None:
    record = ProductRecord(
        source={"name": "TopAI.tools", "url": "https://topai.tools/browse"},
        content={
            "productName": "ChatGPT",
            "startupName": "OpenAI",
            "pricingModel": "FREEMIUM",
            "sourceUrl": "https://topai.tools/s/chatgpt",
        },
    )
    assert record.content.pricing_model is PricingModel.FREEMIUM

    with pytest.raises(ValidationError):
        ProductRecord(
            source={"name": "TopAI.tools", "url": "https://topai.tools/browse"},
            content={
                "productName": "ChatGPT",
                "startupName": "OpenAI",
                "pricingModel": "UNKNOWN",
                "sourceUrl": "https://topai.tools/s/chatgpt",
            },
        )


def test_research_paper_requires_authors_and_aware_publication_date() -> None:
    record = ResearchPaperRecord(
        source={"name": "arXiv", "url": "https://arxiv.org/abs/1706.03762"},
        content={
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani"],
            "paper_url": "https://arxiv.org/abs/1706.03762",
            "github_url": "https://github.com/tensorflow/tensor2tensor",
            "github_stars": 14000,
            "published_date": datetime(2017, 6, 12, tzinfo=timezone.utc),
        },
    )
    assert record.natural_key().startswith("RESEARCH_PAPER:".lower())

    with pytest.raises(ValidationError):
        ResearchPaperRecord(
            content={
                "title": "No Authors",
                "authors": [],
                "paper_url": "https://arxiv.org/abs/0000.00000",
                "published_date": datetime(2026, 8, 11),
            },
        )


def test_job_and_news_dates_must_be_timezone_aware() -> None:
    aware = datetime(2026, 8, 11, 10, tzinfo=timezone.utc)
    JobRecord(
        content={
            "company": "OpenAI",
            "rawCompany": "OpenAI, Inc.",
            "roleTitle": "Senior ML Engineer",
            "normalizedRole": "senior ml engineer",
            "roleFamily": "ML Engineer",
            "isRemote": True,
            "postedDate": aware,
            "sourceName": "AIJobs.com",
            "sourceUrl": "https://aijobs.com/job/1",
        }
    )
    NewsRecord(
        content={
            "title": "AI News",
            "content": "Source-backed content.",
            "publicationDate": aware,
            "sourceName": "TechCrunch AI",
            "sourceUrl": "https://example.com/news",
            "dateSource": "meta_article",
            "contentHash": "abcd1234hash",
        }
    )

    with pytest.raises(ValidationError):
        JobRecord(content={"company": "OpenAI", "date": datetime(2026, 8, 11), "is_remote": True, "role_family": "Engineering"})

