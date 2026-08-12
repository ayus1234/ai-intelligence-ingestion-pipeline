"""Content sizing and chunking for LLM payloads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContentChunk:
    index: int
    text: str
    token_estimate: int
    preserved_prefix: str = ""


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def chunk_text(
    text: str,
    max_tokens: int,
    preserved_prefix: str = "",
    overlap_tokens: int = 80,
) -> list[ContentChunk]:
    """Split text into chunks while carrying important metadata into every chunk."""

    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    prefix_budget = estimate_tokens(preserved_prefix)
    body_budget = max_tokens - prefix_budget
    if body_budget <= 0:
        raise ValueError("preserved_prefix consumes the entire token budget")

    if estimate_tokens(text) + prefix_budget <= max_tokens:
        return [ContentChunk(index=0, text=text, token_estimate=estimate_tokens(text) + prefix_budget, preserved_prefix=preserved_prefix)]

    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[ContentChunk] = []
    current: list[str] = []
    current_tokens = 0
    previous_tail = ""
    overlap_chars = overlap_tokens * 4

    def flush() -> None:
        nonlocal current, current_tokens, previous_tail
        if not current:
            return
        body = "\n\n".join(current).strip()
        if previous_tail:
            body = f"{previous_tail}\n\n{body}"
        chunks.append(
            ContentChunk(
                index=len(chunks),
                text=body,
                token_estimate=estimate_tokens(body) + prefix_budget,
                preserved_prefix=preserved_prefix,
            )
        )
        previous_tail = body[-overlap_chars:] if overlap_chars > 0 else ""
        current = []
        current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph)
        if paragraph_tokens > body_budget:
            flush()
            chars_per_chunk = body_budget * 4
            for start in range(0, len(paragraph), chars_per_chunk):
                body = paragraph[start : start + chars_per_chunk].strip()
                if previous_tail:
                    body = f"{previous_tail}\n\n{body}"
                chunks.append(
                    ContentChunk(
                        index=len(chunks),
                        text=body,
                        token_estimate=estimate_tokens(body) + prefix_budget,
                        preserved_prefix=preserved_prefix,
                    )
                )
                previous_tail = body[-overlap_chars:] if overlap_chars > 0 else ""
            continue
        if current and current_tokens + paragraph_tokens > body_budget:
            flush()
        current.append(paragraph)
        current_tokens += paragraph_tokens
    flush()
    return chunks

