"""Papers With Code mapping crawler via Hugging Face dataset viewer API."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from ai_intel.config import Settings
from ai_intel.schemas import PaperCodeMapping, PaperCodeRepository
from ai_intel.utils import HttpRequestError, RetryPolicy
from ai_intel.utils.arxiv import extract_arxiv_id
from ai_intel.utils.github import normalize_github_repo_url


class PapersWithCodeCrawler:
    source_name = "Papers With Code"
    dataset_rows_base_url = "https://datasets-server.huggingface.co/rows"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=4, base_delay_seconds=1)

    def build_rows_url(self, offset: int, length: int) -> str:
        params = {
            "dataset": self.settings.papers_with_code_dataset,
            "config": self.settings.papers_with_code_config,
            "split": self.settings.papers_with_code_split,
            "offset": offset,
            "length": min(100, length),
        }
        return f"{self.dataset_rows_base_url}?{urlencode(params)}"

    async def fetch_mappings(
        self,
        session: Any,
        limit: int = 1000,
        page_size: int = 100,
    ) -> dict[str, PaperCodeMapping]:
        mappings: dict[str, PaperCodeMapping] = {}
        offset = 0
        while offset < limit:
            length = min(page_size, limit - offset)
            url = self.build_rows_url(offset=offset, length=length)
            try:
                payload = await self.retry_policy.run_async(
                    lambda url=url: self._fetch_json(session, url),
                    is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
                )
                page_mappings = self.parse_payload(payload)
                for mapping in page_mappings:
                    key = mapping.paper_arxiv_id or _mapping_url_key(mapping)
                    if key is None:
                        continue
                    existing = mappings.get(key)
                    if existing is None:
                        mappings[key] = mapping
                    else:
                        existing.repositories.extend(mapping.repositories)
                row_count = _row_count(payload)
                if row_count < length:
                    break
                offset += row_count
            except Exception:
                break
        return mappings

    async def _fetch_json(self, session: Any, url: str) -> dict[str, Any] | list[dict[str, Any]]:
        async with session.get(url) as response:
            if response.status in {408, 429, 500, 502, 503, 504}:
                raise HttpRequestError(
                    "Papers With Code request failed temporarily",
                    status_code=response.status,
                    retryable=True,
                )
            if response.status >= 400:
                raise HttpRequestError(
                    "Papers With Code request failed permanently",
                    status_code=response.status,
                    retryable=False,
                )
            try:
                payload: dict[str, Any] | list[dict[str, Any]] = await response.json()
                if isinstance(payload, (dict, list)):
                    return payload
                return {}
            except Exception as exc:
                raise HttpRequestError("Failed to parse JSON response", retryable=True) from exc

    @staticmethod
    def parse_payload(payload: dict[str, Any] | list[dict[str, Any]]) -> list[PaperCodeMapping]:
        rows = _extract_rows(payload)
        grouped: dict[str, PaperCodeMapping] = {}
        for row in rows:
            repo_url = row.get("repo_url")
            normalized_repo = normalize_github_repo_url(repo_url)
            if normalized_repo is None:
                continue
            paper_arxiv_id = (
                row.get("paper_arxiv_id")
                or extract_arxiv_id(row.get("paper_url_abs"))
                or extract_arxiv_id(row.get("paper_url_pdf"))
            )
            if paper_arxiv_id:
                paper_arxiv_id = extract_arxiv_id(paper_arxiv_id)
            mapping = PaperCodeMapping(
                paper_url=row.get("paper_url"),
                paper_url_abs=row.get("paper_url_abs"),
                paper_title=row.get("paper_title"),
                paper_arxiv_id=paper_arxiv_id,
                papers_with_code_id=_extract_pwc_id(row.get("paper_url")),
                repositories=[
                    PaperCodeRepository(
                        repo_url=normalized_repo.html_url,
                        is_official=row.get("is_official"),
                        mentioned_in_paper=row.get("mentioned_in_paper"),
                        mentioned_in_github=row.get("mentioned_in_github"),
                        framework=row.get("framework"),
                    )
                ],
            )
            key = mapping.paper_arxiv_id or _mapping_url_key(mapping)
            if key is None:
                continue
            if key in grouped:
                grouped[key].repositories.extend(mapping.repositories)
            else:
                grouped[key] = mapping
        return list(grouped.values())


def _extract_rows(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    rows = payload.get("rows")
    if isinstance(rows, list):
        result: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("row"), dict):
                result.append(row["row"])
            elif isinstance(row, dict):
                result.append(row)
        return result
    return []


def _row_count(payload: dict[str, Any] | list[dict[str, Any]]) -> int:
    return len(_extract_rows(payload))


def _extract_pwc_id(paper_url: str | None) -> str | None:
    if not paper_url:
        return None
    slug = paper_url.rstrip("/").split("/")[-1]
    return slug or None


def _mapping_url_key(mapping: PaperCodeMapping) -> str | None:
    if mapping.paper_url_abs:
        return str(mapping.paper_url_abs).lower()
    if mapping.paper_url:
        return str(mapping.paper_url).lower()
    return None
