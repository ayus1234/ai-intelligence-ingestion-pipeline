"""GitHub repository metrics client."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai_intel.config import Settings
from ai_intel.schemas import GitHubRepoMetrics
from ai_intel.utils import HttpRequestError, RetryPolicy, sha256_text
from ai_intel.utils.github import NormalizedGitHubRepo, normalize_github_repo_url


class GitHubMetricsClient:
    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=4, base_delay_seconds=1)

    async def fetch_metrics(self, session: Any, repo_url: str) -> GitHubRepoMetrics | None:
        normalized = normalize_github_repo_url(repo_url)
        if normalized is None:
            return None
        return await self.retry_policy.run_async(
            lambda: self._request_metrics(session, normalized),
            is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
        )

    async def _request_metrics(
        self,
        session: Any,
        normalized: NormalizedGitHubRepo,
    ) -> GitHubRepoMetrics:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.settings.github_api_version,
            "User-Agent": self.settings.crawl_user_agent,
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"

        async with session.get(normalized.api_url, headers=headers) as response:
            payload = await response.json()
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            if response.status in {403, 408, 429, 500, 502, 503, 504}:
                raise HttpRequestError(
                    "GitHub metrics request failed temporarily",
                    status_code=response.status,
                    retryable=True,
                    retry_after_seconds=retry_after,
                )
            if response.status >= 400:
                raise HttpRequestError(
                    "GitHub metrics request failed permanently",
                    status_code=response.status,
                    retryable=False,
                )
            stars = payload.get("stargazers_count")
            if not isinstance(stars, int):
                raise HttpRequestError("GitHub response missing stargazers_count", retryable=False)
            license_payload = payload.get("license")
            license_value = None
            if isinstance(license_payload, dict):
                license_value = license_payload.get("spdx_id") or license_payload.get("name")
            return GitHubRepoMetrics(
                github_url=normalized.html_url,
                owner=normalized.owner,
                repo=normalized.repo,
                stars=stars,
                forks=_optional_int(payload.get("forks_count")),
                watchers=_optional_int(payload.get("watchers_count") or payload.get("watchers")),
                open_issues=_optional_int(payload.get("open_issues_count")),
                default_branch=payload.get("default_branch") if isinstance(payload.get("default_branch"), str) else None,
                archived=payload.get("archived") if isinstance(payload.get("archived"), bool) else None,
                license=license_value if isinstance(license_value, str) else None,
                fetched_at=datetime.now(timezone.utc),
                api_status=response.status,
                response_hash=sha256_text(str(payload)),
            )


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
