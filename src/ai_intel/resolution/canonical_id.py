"""Canonical Entity ID generation rules."""

from __future__ import annotations

import re


def generate_canonical_id(entity_type: str, name: str) -> str:
    """Generate stable canonical entity ID (e.g. 'OpenAI, Inc.' -> 'ent_startup_openai')."""
    if not name:
        return f"ent_{entity_type.lower().strip()}_unknown"

    prefix = f"ent_{entity_type.lower().strip()}"
    clean_name = name.lower().strip()
    # Strip legal suffixes
    clean_name = re.sub(
        r"\b(inc|corp|corporation|llc|ltd|limited|co|company|gmbh|ai|labs|lab|technologies|solutions|systems)\b\.?",
        "",
        clean_name,
    )
    # Convert non-alphanumeric chars to underscore
    clean_name = re.sub(r"[^a-z0-9]+", "_", clean_name).strip("_")
    return f"{prefix}_{clean_name}" if clean_name else f"{prefix}_unknown"
