"""Tests for ExtractionCache."""

from ai_intel.llm import ExtractionCache


def test_extraction_cache_operations() -> None:
    cache = ExtractionCache()
    key = ExtractionCache.compute_key("sample document text", "startup")
    assert cache.get(key) is None

    payload = {"entityName": "OpenAI", "employeeCount": 1000}
    cache.set(key, payload)

    cached = cache.get(key)
    assert cached == payload
    assert len(cache) == 1

    cache.clear()
    assert len(cache) == 0
