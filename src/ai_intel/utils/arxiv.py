"""arXiv identifier helpers."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_ARXIV_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)
_NEW_STYLE_RE = re.compile(r"^\d{4}\.\d{4,5}(?:v\d+)?$", re.IGNORECASE)
_OLD_STYLE_RE = re.compile(r"^[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?$", re.IGNORECASE)


def strip_arxiv_version(arxiv_id: str) -> str:
    return _ARXIV_VERSION_RE.sub("", arxiv_id.strip())


def extract_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.lower().startswith("arxiv:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    if _NEW_STYLE_RE.match(cleaned) or _OLD_STYLE_RE.match(cleaned):
        return strip_arxiv_version(cleaned)

    parts = urlsplit(cleaned)
    path = parts.path.strip("/")
    if not path:
        return None
    if path.startswith("abs/") or path.startswith("pdf/"):
        candidate = path.split("/", 1)[1]
    else:
        candidate = path
    if candidate.endswith(".pdf"):
        candidate = candidate[:-4]
    if _NEW_STYLE_RE.match(candidate) or _OLD_STYLE_RE.match(candidate):
        return strip_arxiv_version(candidate)
    return None


def canonical_arxiv_abs_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{strip_arxiv_version(arxiv_id)}"


def normalize_title_for_join(title: str | None) -> str:
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
