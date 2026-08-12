"""Structured extraction cache engine."""

from __future__ import annotations

from typing import Any

from ai_intel.utils.hashing import sha256_text


class ExtractionCache:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def compute_key(content: str, schema_name: str, prompt_version: str = "v1") -> str:
        """Compute sha256 content hash key for extraction caching."""
        normalized = f"{content.strip()}\n{schema_name.lower().strip()}\n{prompt_version.strip()}"
        return sha256_text(normalized)

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve cached structured extraction payload if present."""
        return self._cache.get(key)

    def set(self, key: str, payload: dict[str, Any]) -> None:
        """Store structured extraction payload in cache."""
        self._cache[key] = payload

    def clear(self) -> None:
        """Clear extraction cache."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
