"""Y Combinator startup ingestion."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from ai_intel.config import Settings
from ai_intel.schemas import StartupCandidate
from ai_intel.utils import HttpRequestError, RetryPolicy


class YCombinatorCrawler:
    source_name = "Y Combinator"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=4, base_delay_seconds=1)

    async def fetch_startups(self, session: Any, limit: int) -> list[StartupCandidate]:
        payload = await self.retry_policy.run_async(
            lambda: self._fetch_json(session, self.settings.yc_companies_endpoint),
            is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
        )
        return self.parse_payload(payload, limit=limit)

    async def _fetch_json(self, session: Any, url: str) -> list[dict[str, Any]]:
        async with session.get(url) as response:
            if response.status in {408, 429, 500, 502, 503, 504}:
                raise HttpRequestError(
                    "Y Combinator request failed temporarily",
                    status_code=response.status,
                    retryable=True,
                )
            if response.status >= 400:
                raise HttpRequestError(
                    "Y Combinator request failed permanently",
                    status_code=response.status,
                    retryable=False,
                )
            try:
                payload = await response.json(content_type=None)
            except Exception as exc:
                raise HttpRequestError("Failed to parse Y Combinator JSON payload", retryable=True) from exc
            if not isinstance(payload, list):
                raise HttpRequestError("Y Combinator response was not a list", retryable=False)
            return payload

    @classmethod
    def parse_payload(cls, payload: list[dict[str, Any]], limit: int) -> list[StartupCandidate]:
        startups: list[StartupCandidate] = []
        collected_at = datetime.now(timezone.utc)
        for item in payload:
            try:
                name = item.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue
                source_url = _source_url(item)
                website_raw = item.get("website") if isinstance(item.get("website"), str) else None
                website = _normalize_website_url(website_raw)
                team_size = item.get("team_size")
                employee_count = team_size if isinstance(team_size, int) and team_size >= 0 else None
                startups.append(
                    StartupCandidate(
                        raw_name=name.strip(),
                        source_name=cls.source_name,
                        source_url=source_url,
                        website_url=website,
                        company_domain=_domain_from_url(website),
                        employee_count=employee_count,
                        employee_count_raw=str(team_size) if employee_count is not None else None,
                        batch=item.get("batch") if isinstance(item.get("batch"), str) else None,
                        industry=item.get("industry") if isinstance(item.get("industry"), str) else None,
                        source_payload=_safe_payload(item),
                        source_collected_at=collected_at,
                    )
                )
            except Exception:
                continue
            if len(startups) >= limit:
                break
        return startups


def _source_url(item: dict[str, Any]) -> str:
    url = item.get("url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    slug = item.get("slug")
    if isinstance(slug, str) and slug:
        return f"https://www.ycombinator.com/companies/{slug}"
    return "https://www.ycombinator.com/companies"


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    netloc = urlsplit(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def _normalize_website_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if cleaned in {"http://", "https://", "http:///", "https:///"}:
        return None
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    if cleaned.startswith("http://") and len(cleaned) <= 7:
        return None
    if cleaned.startswith("https://") and len(cleaned) <= 8:
        return None
    return cleaned


def _safe_payload(item: dict[str, Any]) -> dict[str, object]:
    keys = ("id", "slug", "former_names", "one_liner", "batch", "industry", "subindustry", "status", "stage")
    return {key: value for key in keys if (value := item.get(key)) is not None}
