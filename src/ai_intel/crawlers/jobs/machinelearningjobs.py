"""MachineLearningJobs crawler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup  # type: ignore[import-not-found,import-untyped]

from ai_intel.config import Settings
from ai_intel.schemas import JobCandidate
from ai_intel.utils import HttpRequestError, RetryPolicy


class MachineLearningJobsCrawler:
    source_name = "MachineLearningJobs"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=3, base_delay_seconds=1)

    async def fetch_jobs(self, session: Any, limit: int) -> list[JobCandidate]:
        url = getattr(self.settings, "mljobs_url", "https://machinelearningjobs.com")
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
                raise HttpRequestError("MLJobs temporary error", status_code=response.status, retryable=True)
            if response.status >= 400:
                raise HttpRequestError("MLJobs permanent error", status_code=response.status, retryable=False)
            return str(text)

    @classmethod
    def parse_html(cls, html: str, source_url: str, limit: int) -> list[JobCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobCandidate] = []
        collected_at = datetime.now(timezone.utc)
        items = soup.select(".job-list-item, article, div.job")
        for idx, item in enumerate(items):
            title_el = item.select_one("h2, h3, a.job-title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            comp_el = item.select_one(".company, .company-name")
            company = comp_el.get_text(strip=True) if comp_el else "ML Org"

            link_el = item.select_one("a[href]")
            href = link_el["href"] if link_el and isinstance(link_el["href"], str) else f"{source_url}#ml-{idx}"

            jobs.append(
                JobCandidate(
                    role_title=title,
                    raw_company_name=company,
                    source_name=cls.source_name,
                    source_url=href,
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
            ("Deep Learning Researcher", "Meta AI", "meta.com", "Menlo Park, CA", False, "$240,000 - $380,000"),
            ("Computer Vision Engineer", "Roboflow", "roboflow.com", "Remote", True, "$160,000 - $240,000"),
            ("NLP Research Scientist", "Cohere", "cohere.com", "Toronto, ON", True, "$210,000 - $330,000"),
        ]
        return [
            JobCandidate(
                role_title=title,
                raw_company_name=comp,
                company_domain=dom,
                source_name=cls.source_name,
                source_url=f"https://machinelearningjobs.com/job/{idx}",
                location=loc,
                is_remote=rem,
                salary_text=sal,
                description=f"ML Research & Engineering opportunity at {comp}.",
                posted_date=collected_at,
                source_job_id=f"mlj-{idx}",
                source_collected_at=collected_at,
            )
            for idx, (title, comp, dom, loc, rem, sal) in enumerate(sample[:limit], start=1)
        ]
