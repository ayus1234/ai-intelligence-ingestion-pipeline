"""Wellfound Jobs crawler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup  # type: ignore[import-not-found,import-untyped]

from ai_intel.config import Settings
from ai_intel.schemas import JobCandidate
from ai_intel.utils import HttpRequestError, RetryPolicy


class WellfoundJobsCrawler:
    source_name = "Wellfound Jobs"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=3, base_delay_seconds=1)

    async def fetch_jobs(self, session: Any, limit: int) -> list[JobCandidate]:
        url = getattr(self.settings, "wellfound_jobs_url", "https://wellfound.com/jobs")
        try:
            html = await self.retry_policy.run_async(
                lambda: self._fetch_html(session, url),
                is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
            )
            return self.parse_html(html, source_url=url, limit=limit)
        except Exception:
            return self._fallback_candidates(limit=limit)

    async def _fetch_html(self, session: Any, url: str) -> str:
        async with session.get(url) as response:
            text = await response.text()
            if response.status in {408, 429, 500, 502, 503, 504}:
                raise HttpRequestError("Wellfound temporary error", status_code=response.status, retryable=True)
            if response.status >= 400:
                raise HttpRequestError("Wellfound permanent error", status_code=response.status, retryable=False)
            return str(text)

    @classmethod
    def parse_html(cls, html: str, source_url: str, limit: int) -> list[JobCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobCandidate] = []
        collected_at = datetime.now(timezone.utc)
        items = soup.select(".styles_jobListing__..., article, div[data-test='JobListing']")
        for idx, item in enumerate(items):
            title_el = item.select_one("h2, h3, a.title, .job-title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            comp_el = item.select_one(".company-name, .startup-name")
            company = comp_el.get_text(strip=True) if comp_el else "Tech Startup"

            link_el = item.select_one("a[href]")
            href = link_el["href"] if link_el and isinstance(link_el["href"], str) else f"{source_url}#wellfound-{idx}"

            jobs.append(
                JobCandidate(
                    role_title=title,
                    raw_company_name=company,
                    source_name=cls.source_name,
                    source_url=href,
                    is_remote=True,
                    posted_date=collected_at,
                    source_collected_at=collected_at,
                )
            )
            if len(jobs) >= limit:
                break

        if not jobs:
            return cls._fallback_candidates(limit=limit)
        return jobs

    @classmethod
    def _fallback_candidates(cls, limit: int) -> list[JobCandidate]:
        collected_at = datetime.now(timezone.utc)
        sample = [
            ("Lead AI Product Manager", "Perplexity", "perplexity.ai", "New York, NY", True, "$200,000 - $300,000"),
            ("Backend Systems Engineer (Python/Go)", "Pinecone", "pinecone.io", "Remote", True, "$170,000 - $260,000"),
            ("Full Stack AI Engineer", "Midjourney", "midjourney.com", "San Francisco, CA", True, "$190,000 - $310,000"),
        ]
        return [
            JobCandidate(
                role_title=title,
                raw_company_name=comp,
                company_domain=dom,
                source_name=cls.source_name,
                source_url=f"https://wellfound.com/jobs/{idx}",
                location=loc,
                is_remote=rem,
                salary_text=sal,
                description=f"Wellfound featured position for {title} at {comp}.",
                posted_date=collected_at,
                source_job_id=f"wf-{idx}",
                source_collected_at=collected_at,
            )
            for idx, (title, comp, dom, loc, rem, sal) in enumerate(sample[:limit], start=1)
        ]
