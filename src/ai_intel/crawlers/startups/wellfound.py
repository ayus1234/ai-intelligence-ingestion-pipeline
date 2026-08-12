"""Wellfound enrichment parser for startup employee-count hints."""

from __future__ import annotations

from typing import Any

from ai_intel.config import Settings
from ai_intel.extraction import clean_html, extract_employee_phrase, parse_employee_count
from ai_intel.resolution import normalize_entity_name
from ai_intel.schemas import StartupEnrichment
from ai_intel.utils import HttpRequestError, RetryPolicy


class WellfoundStartupEnricher:
    source_name = "Wellfound"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=3, base_delay_seconds=1)

    async def fetch_enrichments(self, session: Any) -> dict[str, StartupEnrichment]:
        html = await self.retry_policy.run_async(
            lambda: self._fetch_html(session, self.settings.wellfound_jobs_url),
            is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
        )
        return self.parse_html(html, source_url=self.settings.wellfound_jobs_url)

    async def _fetch_html(self, session: Any, url: str) -> str:
        async with session.get(url) as response:
            text = await response.text()
            if response.status in {408, 429, 500, 502, 503, 504}:
                raise HttpRequestError(
                    "Wellfound request failed temporarily",
                    status_code=response.status,
                    retryable=True,
                )
            if response.status >= 400:
                raise HttpRequestError(
                    "Wellfound request failed permanently",
                    status_code=response.status,
                    retryable=False,
                )
            return text

    @classmethod
    def parse_html(cls, html: str, source_url: str) -> dict[str, StartupEnrichment]:
        text = clean_html(html)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        enrichments: dict[str, StartupEnrichment] = {}
        previous_line: str | None = None
        for line in lines:
            phrase = extract_employee_phrase(line)
            if phrase and previous_line and _looks_like_company_name(previous_line):
                enrichment = StartupEnrichment(
                    raw_name=previous_line,
                    source_name=cls.source_name,
                    source_url=source_url,
                    employee_count=parse_employee_count(phrase),
                    employee_count_raw=phrase,
                )
                enrichments[normalize_entity_name(previous_line)] = enrichment
            if not phrase:
                previous_line = line
        return enrichments


def _looks_like_company_name(value: str) -> bool:
    lowered = value.lower()
    blocked = {
        "remote jobs",
        "featured lists",
        "trending startups hiring now",
        "find what's next:",
    }
    return lowered not in blocked and len(value) <= 80
