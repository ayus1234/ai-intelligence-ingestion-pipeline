from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ai_intel.schemas import CrawlTarget, RawDocument, StartupRecord
from ai_intel.storage import InMemoryStorageRepository
from ai_intel.utils.hashing import sha256_text


@pytest.mark.asyncio
async def test_in_memory_storage_deduplicates_targets_and_records() -> None:
    storage = InMemoryStorageRepository()
    target = CrawlTarget(
        url="https://example.com/path?utm_source=x",
        source_name="Example",
        source_kind="news",
    )
    duplicate = CrawlTarget(
        url="https://example.com/path/",
        source_name="Example",
        source_kind="news",
    )

    assert await storage.enqueue(target) is True
    assert await storage.enqueue(duplicate) is False
    assert await storage.claim_batch(10) == [target]

    raw = RawDocument(
        source_name="Example",
        source_url="https://example.com/path",
        fetched_at=datetime.now(timezone.utc),
        http_status=200,
        raw_html="<p>Hello</p>",
        content_hash=sha256_text("Hello"),
    )
    assert await storage.save_raw(raw) is True
    assert await storage.save_raw(raw) is False

    record = StartupRecord(
        source={"name": "Example", "url": "https://example.com/path"},
        content={"entityName": "OpenAI", "data": {"employeeCount": 1000}},
    )
    assert await storage.upsert_record(record) is True
    assert await storage.upsert_record(record) is False

