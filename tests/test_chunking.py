from __future__ import annotations

from ai_intel.extraction import chunk_text, estimate_tokens


def test_chunk_text_keeps_metadata_prefix_and_splits_large_content() -> None:
    prefix = "title: Important article\nurl: https://example.com/article"
    text = "\n\n".join(f"paragraph {idx} " + ("word " * 60) for idx in range(12))

    chunks = chunk_text(text, max_tokens=120, preserved_prefix=prefix, overlap_tokens=5)

    assert len(chunks) > 1
    assert all(chunk.preserved_prefix == prefix for chunk in chunks)
    assert all(chunk.token_estimate <= 140 for chunk in chunks)
    assert "paragraph 0" in chunks[0].text


def test_estimate_tokens_is_stable() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2

