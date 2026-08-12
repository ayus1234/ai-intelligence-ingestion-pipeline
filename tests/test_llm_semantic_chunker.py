"""Tests for SemanticChunker and token estimation."""

from ai_intel.llm import SemanticChunker, estimate_tokens


def test_estimate_tokens() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("Hello World") > 0


def test_semantic_chunker_small_text() -> None:
    chunker = SemanticChunker(max_tokens_per_chunk=100)
    text = "# Section 1\n\nShort text block."
    chunks = chunker.chunk(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_semantic_chunker_large_text() -> None:
    chunker = SemanticChunker(max_tokens_per_chunk=20)
    text = (
        "# Main Title\n\n"
        "Paragraph 1 contains a long discussion about artificial intelligence architectures.\n\n"
        "Paragraph 2 discusses distributed training pipelines and GPU cluster optimization.\n\n"
        "Paragraph 3 concludes with evaluation metrics on downstream benchmarks."
    )
    chunks = chunker.chunk(text)
    assert len(chunks) > 1
    assert "[Context: # Main Title]" in chunks[1]
