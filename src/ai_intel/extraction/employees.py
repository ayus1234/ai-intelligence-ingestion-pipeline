"""Employee-count parsing without estimating ranges."""

from __future__ import annotations

import re

EMPLOYEE_PHRASE_RE = re.compile(
    r"(?P<raw>(?:\d[\d,]*\s*(?:[-–]\s*\d[\d,]*|\+)?|\d[\d,]*)\s+employees?)",
    re.IGNORECASE,
)


def parse_employee_count(value: object) -> int | None:
    if isinstance(value, int) and value >= 0:
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    if "+" in text or "-" in text or "–" in text:
        return None
    match = re.search(r"\b(\d[\d,]*)\s+employees?\b", text)
    if not match:
        if re.fullmatch(r"\d[\d,]*", text):
            return int(text.replace(",", ""))
        return None
    return int(match.group(1).replace(",", ""))


def extract_employee_phrase(text: str) -> str | None:
    match = EMPLOYEE_PHRASE_RE.search(text)
    return match.group("raw") if match else None
