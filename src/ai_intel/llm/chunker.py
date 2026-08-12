"""Semantic adaptive chunking engine for large documents."""

from __future__ import annotations

import re


def estimate_tokens(text: str) -> int:
    """Estimate token count for a text string (~4 characters per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class SemanticChunker:
    def __init__(self, max_tokens_per_chunk: int = 4000) -> None:
        self.max_tokens_per_chunk = max_tokens_per_chunk

    def chunk(self, text: str) -> list[str]:
        """Split text into semantic chunks respecting headers, paragraphs, and lists."""
        if not text:
            return []

        if estimate_tokens(text) <= self.max_tokens_per_chunk:
            return [text]

        # Extract title or initial header as context header
        lines = text.splitlines()
        header_context = ""
        for line in lines[:5]:
            if line.startswith("#") or "title" in line.lower():
                header_context = line.strip()
                break

        # Split into semantic blocks (headings, paragraphs, lists, tables)
        raw_blocks = re.split(r"\n\s*\n", text)
        blocks: list[str] = [b.strip() for b in raw_blocks if b.strip()]

        chunks: list[str] = []
        current_blocks: list[str] = []
        current_tokens = 0

        for block in blocks:
            block_tokens = estimate_tokens(block)
            if current_tokens + block_tokens > self.max_tokens_per_chunk and current_blocks:
                chunk_text = "\n\n".join(current_blocks)
                chunks.append(chunk_text)

                current_blocks = []
                current_tokens = 0
                if header_context and not block.startswith("#"):
                    current_blocks.append(f"[Context: {header_context}]")
                    current_tokens += estimate_tokens(header_context)

            current_blocks.append(block)
            current_tokens += block_tokens

        if current_blocks:
            chunks.append("\n\n".join(current_blocks))

        return chunks
