from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ai_intel.schemas import ResearchPaperRecord
from ai_intel.validation import RecordValidationError, RecordValidator


def test_validator_accepts_valid_research_paper() -> None:
    record = ResearchPaperRecord(
        source={"name": "arXiv", "url": "https://arxiv.org/abs/1706.03762"},
        content={
            "arxiv_id": "1706.03762",
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani"],
            "paper_url": "https://arxiv.org/abs/1706.03762",
            "published_date": datetime(2017, 6, 12, tzinfo=timezone.utc),
        },
    )

    RecordValidator().validate(record)


def test_validator_rejects_future_publication_date() -> None:
    record = ResearchPaperRecord(
        source={"name": "arXiv", "url": "https://arxiv.org/abs/9999.99999"},
        content={
            "arxiv_id": "9999.99999",
            "title": "Future Paper",
            "authors": ["Author"],
            "paper_url": "https://arxiv.org/abs/9999.99999",
            "published_date": datetime.now(timezone.utc) + timedelta(days=1),
        },
    )

    with pytest.raises(RecordValidationError) as error:
        RecordValidator().validate(record)

    assert error.value.issues[0].field == "content.published_date"

