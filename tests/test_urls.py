from __future__ import annotations

from ai_intel.utils.hashing import sha256_text
from ai_intel.utils.urls import normalize_url


def test_normalize_url_removes_tracking_and_fragment() -> None:
    normalized = normalize_url("HTTPS://Example.COM:443/path/?b=2&utm_source=x&a=1#section")
    assert normalized == "https://example.com/path?a=1&b=2"


def test_hash_is_deterministic_for_normalized_url() -> None:
    left = sha256_text(normalize_url("https://example.com/path?utm_medium=x&a=1"))
    right = sha256_text(normalize_url("https://EXAMPLE.com/path/?a=1"))
    assert left == right

