"""Deterministic company/product name normalization."""

from __future__ import annotations

import re
import unicodedata


LEGAL_SUFFIXES = {
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "plc",
    "pvt",
    "private",
    "company",
    "co",
}


def normalize_entity_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    tokens = [token for token in normalized.split() if token not in LEGAL_SUFFIXES]
    compact = "".join(tokens)
    return compact


def clean_canonical_name(name: str) -> str:
    """Strip legal entity suffixes (LLC, Corporation, Inc, Ltd, etc.) to return a clean canonical entity name."""
    if not name:
        return ""
    # Strip parenthetical metadata like (YC W12), (YC S11)
    cleaned = re.sub(r"\s*\([^)]*\)", "", name).strip()
    # Strip legal suffixes at the end of the string
    pattern = r"\s+\b(LLC|Corporation|Corp\.?|Inc\.?|Ltd\.?|Limited|PBC|GmbH|SAS|B\.V\.?|Group\s+Inc\.?|Technologies|Co\.?|Pty|Pvt)\b.*$"
    cleaned_suffix = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned_suffix if cleaned_suffix else cleaned


