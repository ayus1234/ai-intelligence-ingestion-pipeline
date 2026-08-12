"""Publication date extraction and 24-hour freshness gate."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any


@dataclass(frozen=True, slots=True)
class DateEvidence:
    value: datetime
    source: str
    raw: str


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    is_accepted: bool
    published_at: datetime | None
    evidence_source: str | None
    reason: str


class _DateHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta_values: list[tuple[str, str]] = []
        self.time_values: list[str] = []
        self.json_ld: list[str] = []
        self._capture_json_ld = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value for key, value in attrs if value is not None}
        if tag == "meta":
            key = attr_map.get("property") or attr_map.get("name") or attr_map.get("itemprop")
            content = attr_map.get("content")
            if key and content:
                self.meta_values.append((key.lower(), content))
        if tag == "time":
            datetime_value = attr_map.get("datetime")
            if datetime_value:
                self.time_values.append(datetime_value)
        if tag == "script" and attr_map.get("type", "").lower() == "application/ld+json":
            self._capture_json_ld = True
            self._json_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture_json_ld:
            self._capture_json_ld = False
            self.json_ld.append("".join(self._json_parts))
            self._json_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_json_ld:
            self._json_parts.append(data)


def _parse_datetime(raw: str, base_time: datetime) -> datetime | None:
    text = raw.strip()
    lower = text.lower()
    relative = re.match(r"^(\d+)\s+(minute|minutes|hour|hours|day|days)\s+ago$", lower)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if unit.startswith("minute"):
            return base_time - timedelta(minutes=amount)
        if unit.startswith("hour"):
            return base_time - timedelta(hours=amount)
        if unit.startswith("day"):
            return base_time - timedelta(days=amount)

    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _jsonld_dates(payload: Any) -> list[tuple[str, str]]:
    dates: list[tuple[str, str]] = []
    if isinstance(payload, list):
        for item in payload:
            dates.extend(_jsonld_dates(item))
    elif isinstance(payload, dict):
        for key in ("datePublished", "dateCreated", "uploadDate"):
            value = payload.get(key)
            if isinstance(value, str):
                dates.append((f"jsonld.{key}", value))
        graph = payload.get("@graph")
        if graph:
            dates.extend(_jsonld_dates(graph))
    return dates


def extract_candidate_dates(html_or_text: str, base_time: datetime) -> list[DateEvidence]:
    if base_time.tzinfo is None or base_time.utcoffset() is None:
        raise ValueError("base_time must be timezone-aware")
    base_time = base_time.astimezone(timezone.utc)

    parser = _DateHTMLParser()
    parser.feed(html_or_text)
    parser.close()

    raw_candidates: list[tuple[str, str]] = []
    for raw_json in parser.json_ld:
        try:
            raw_candidates.extend(_jsonld_dates(json.loads(raw_json)))
        except json.JSONDecodeError:
            continue

    priority_meta_keys = {
        "article:published_time",
        "date",
        "dc.date",
        "dc.date.issued",
        "pubdate",
        "publishdate",
        "timestamp",
    }
    raw_candidates.extend(
        (f"meta.{key}", content) for key, content in parser.meta_values if key in priority_meta_keys
    )
    raw_candidates.extend(("time.datetime", value) for value in parser.time_values)

    for match in re.finditer(r"\b\d+\s+(?:minutes?|hours?|days?)\s+ago\b", html_or_text, re.IGNORECASE):
        raw_candidates.append(("visible.relative", match.group(0)))

    seen: set[tuple[str, str]] = set()
    evidence: list[DateEvidence] = []
    for source, raw in raw_candidates:
        key = (source, raw)
        if key in seen:
            continue
        seen.add(key)
        parsed = _parse_datetime(raw, base_time)
        if parsed:
            evidence.append(DateEvidence(value=parsed, source=source, raw=raw))
    return evidence


def is_fresh(
    published_at: datetime | None,
    run_started_at_utc: datetime,
    freshness_window: timedelta = timedelta(hours=24),
) -> FreshnessResult:
    if run_started_at_utc.tzinfo is None or run_started_at_utc.utcoffset() is None:
        raise ValueError("run_started_at_utc must be timezone-aware")
    run_started_at_utc = run_started_at_utc.astimezone(timezone.utc)

    if published_at is None:
        return FreshnessResult(False, None, None, "missing_publication_date")
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ValueError("published_at must be timezone-aware")
    published_at = published_at.astimezone(timezone.utc)

    earliest = run_started_at_utc - freshness_window
    if published_at > run_started_at_utc:
        return FreshnessResult(False, published_at, None, "publication_date_in_future")
    if published_at < earliest:
        return FreshnessResult(False, published_at, None, "older_than_freshness_window")
    return FreshnessResult(True, published_at, None, "fresh")

