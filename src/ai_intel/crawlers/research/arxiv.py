"""Asynchronous arXiv API crawler."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from ai_intel.config import Settings
from ai_intel.schemas import ArxivPaper
from ai_intel.utils import HttpRequestError, RetryPolicy
from ai_intel.utils.arxiv import canonical_arxiv_abs_url, extract_arxiv_id

try:
    import aiohttp  # type: ignore[import-not-found,import-untyped,unused-ignore]
except ImportError:
    aiohttp = None  # type: ignore[assignment]

ATOM = "{http://www.w3.org/2005/Atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"


def _parse_atom_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ArxivCrawler:
    source_name = "arXiv"
    base_url = "https://export.arxiv.org/api/query"

    def __init__(
        self,
        settings: Settings,
        retry_policy: RetryPolicy | None = None,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=4, base_delay_seconds=1)
        self.sleep = sleep

    def build_query_url(self, start: int, max_results: int) -> str:
        params = {
            "search_query": self.settings.arxiv_query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        return f"{self.base_url}?{urlencode(params)}"

    def build_id_list_url(self, arxiv_ids: list[str]) -> str:
        params = {
            "id_list": ",".join(arxiv_ids),
            "start": 0,
            "max_results": len(arxiv_ids),
        }
        return f"{self.base_url}?{urlencode(params)}"

    async def iter_papers(self, limit: int, session: Any | None = None) -> AsyncIterator[ArxivPaper]:
        if limit <= 0:
            return

        owns_session = session is None
        if session is None:
            if aiohttp is None:
                raise RuntimeError("aiohttp is required for HTTP fetching.")

            timeout = aiohttp.ClientTimeout(total=self.settings.default_http_timeout_seconds)
            session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.settings.crawl_user_agent},
            )

        emitted = 0
        start = 0
        try:
            while emitted < limit:
                page_size = min(self.settings.arxiv_page_size, limit - emitted)
                url = self.build_query_url(start=start, max_results=page_size)
                xml_text = await self.retry_policy.run_async(
                    lambda url=url: self._fetch_page(session, url),
                    is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
                )
                papers = self.parse_feed(xml_text)
                if not papers:
                    break
                for paper in papers:
                    yield paper
                    emitted += 1
                    if emitted >= limit:
                        break
                start += len(papers)
                if len(papers) < page_size:
                    break
                await self.sleep(float(self.settings.arxiv_polite_delay_seconds))
        finally:
            if owns_session:
                await session.close()

    async def fetch_papers(self, limit: int, session: Any | None = None) -> list[ArxivPaper]:
        return [paper async for paper in self.iter_papers(limit=limit, session=session)]

    async def fetch_by_ids(
        self,
        arxiv_ids: list[str],
        session: Any,
        batch_size: int = 25,
    ) -> dict[str, ArxivPaper]:
        papers: dict[str, ArxivPaper] = {}
        for start in range(0, len(arxiv_ids), batch_size):
            batch = arxiv_ids[start : start + batch_size]
            url = self.build_id_list_url(batch)
            try:
                xml_text = await self.retry_policy.run_async(
                    lambda url=url: self._fetch_page(session, url),
                    is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
                )
                for paper in self.parse_feed(xml_text):
                    papers[paper.arxiv_id] = paper
            except Exception:
                pass
            if start + batch_size < len(arxiv_ids):
                await self.sleep(float(self.settings.arxiv_polite_delay_seconds))
        return papers

    async def _fetch_page(self, session: Any, url: str) -> str:
        try:
            async with session.get(url) as response:
                body = await response.text()
                if response.status in {408, 429, 500, 502, 503, 504}:
                    raise HttpRequestError(
                        "arXiv request failed temporarily",
                        status_code=response.status,
                        retryable=True,
                    )
                if response.status >= 400:
                    raise HttpRequestError(
                        "arXiv request failed permanently",
                        status_code=response.status,
                        retryable=False,
                    )
                return str(body)
        except HttpRequestError:
            raise
        except Exception as exc:
            raise HttpRequestError(f"arXiv request failed: {exc}", retryable=True) from exc

    @staticmethod
    def parse_feed(xml_text: str) -> list[ArxivPaper]:
        root = ET.fromstring(xml_text)
        papers: list[ArxivPaper] = []
        for entry in root.findall(f"{ATOM}entry"):
            paper_id_url = _required_text(entry, f"{ATOM}id")
            arxiv_id = extract_arxiv_id(paper_id_url)
            if arxiv_id is None:
                continue
            title = _required_text(entry, f"{ATOM}title")
            published = _parse_atom_datetime(_required_text(entry, f"{ATOM}published"))
            updated_text = _optional_text(entry, f"{ATOM}updated")
            updated = _parse_atom_datetime(updated_text) if updated_text else None
            authors = [
                _required_text(author, f"{ATOM}name")
                for author in entry.findall(f"{ATOM}author")
                if _optional_text(author, f"{ATOM}name")
            ]
            categories = [
                category.attrib["term"]
                for category in entry.findall(f"{ATOM}category")
                if category.attrib.get("term")
            ]
            paper_url = _best_abs_url(entry, fallback=canonical_arxiv_abs_url(arxiv_id))
            papers.append(
                ArxivPaper(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    paper_url=paper_url,
                    published_date=published,
                    updated_date=updated,
                    summary=_optional_text(entry, f"{ATOM}summary"),
                    categories=categories,
                )
            )
        return papers

    @staticmethod
    def total_results(xml_text: str) -> int | None:
        root = ET.fromstring(xml_text)
        value = _optional_text(root, f"{OPENSEARCH}totalResults")
        return int(value) if value and value.isdigit() else None


def _optional_text(element: ET.Element, path: str) -> str | None:
    found = element.find(path)
    if found is None or found.text is None:
        return None
    text = found.text.strip()
    return text or None


def _required_text(element: ET.Element, path: str) -> str:
    text = _optional_text(element, path)
    if not text:
        raise ValueError(f"missing required Atom field: {path}")
    return text


def _best_abs_url(entry: ET.Element, fallback: str) -> str:
    for link in entry.findall(f"{ATOM}link"):
        if link.attrib.get("rel") == "alternate" and link.attrib.get("href"):
            return link.attrib["href"]
    return fallback
