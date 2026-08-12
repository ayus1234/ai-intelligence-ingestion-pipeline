"""Tests for batch storage operations."""

from datetime import datetime, timezone

import pytest

from ai_intel.schemas import ProductRecord, StartupRecord
from ai_intel.storage import InMemoryStorageRepository


@pytest.mark.asyncio
async def test_in_memory_batch_upsert() -> None:
    storage = InMemoryStorageRepository()
    now_dt = datetime.now(timezone.utc)

    s1 = StartupRecord(
        content={
            "entityName": "OpenAI",
            "rawEntityName": "OpenAI, Inc.",
            "data": {"employeeCount": 1000},
        }
    )
    s2 = StartupRecord(
        content={
            "entityName": "Anthropic",
            "rawEntityName": "Anthropic AI",
            "data": {"employeeCount": 500},
        }
    )

    count = await storage.batch_upsert_startups([s1, s2])
    assert count == 2
    assert len(storage.records) == 2

    p1 = ProductRecord(
        content={
            "productName": "ChatGPT",
            "startupName": "OpenAI",
            "pricingModel": "FREEMIUM",
            "sourceUrl": "https://chatgpt.com",
        }
    )
    p_count = await storage.batch_upsert_products([p1])
    assert p_count == 1
