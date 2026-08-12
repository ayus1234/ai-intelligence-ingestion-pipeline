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

