"""Tests for NewsPipeline execution and 24h freshness filtering."""

from datetime import datetime, timedelta, timezone

import pytest

from ai_intel.config import Settings
from ai_intel.pipelines.news import NewsPipeline
from ai_intel.schemas import NewsCandidate
from ai_intel.storage import InMemoryStorageRepository


class DummyNewsResponse:
    def __init__(self, text: str, status: int = 200) -> None:
        self._text = text
        self.status = status

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> "DummyNewsResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


class DummyNewsSession:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses

    def get(self, url: str) -> DummyNewsResponse:
        html = self.responses.get(url, "<html><body><p>Article body content text.</p></body></html>")
        return DummyNewsResponse(html)

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_news_pipeline_24h_freshness_filtering() -> None:
    now_dt = datetime.now(timezone.utc)
    fresh_dt = now_dt - timedelta(hours=2)
    stale_dt = now_dt - timedelta(hours=36)

    c_fresh = NewsCandidate(
        title="Fresh AI Breakthrough",
        source_name="TechCrunch AI",
        source_url="https://techcrunch.com/fresh-ai",
        published_date=fresh_dt,
        date_source="rss",
    )
    c_stale = NewsCandidate(
        title="Stale AI News",
        source_name="The Verge AI",
        source_url="https://www.theverge.com/stale-ai",
        published_date=stale_dt,
        date_source="rss",
    )

    storage = InMemoryStorageRepository()
    pipeline = NewsPipeline(settings=Settings(app_env="test"), storage=storage)

    async def mock_fetch(session: object, src: str, url: str, limit: int) -> list[NewsCandidate]:
        return [c_fresh] if "TechCrunch" in src else [c_stale]

    pipeline._fetch_feed_candidates = mock_fetch  # type: ignore[assignment]

    session = DummyNewsSession(
        {
            "https://techcrunch.com/fresh-ai": '<html><head><script type="application/ld+json">{"datePublished":"'
            + fresh_dt.isoformat()
            + '"}</script></head><body><p>Fresh article paragraph body text.</p></body></html>',
            "https://www.theverge.com/stale-ai": '<html><head><script type="application/ld+json">{"datePublished":"'
            + stale_dt.isoformat()
            + '"}</script></head><body><p>Stale article paragraph body text.</p></body></html>',
        }
    )

    result = await pipeline.ingest(hours=24, limit=10, session=session)

    assert result.cutoff_hours == 24
    assert result.fetched_candidates == 5
    assert result.stored_articles == 1
    assert result.rejected_stale == 4
    assert result.verified_articles == 1

    # Stored record check
    stored_rec = list(storage.records.values())[0]
    assert stored_rec.content.title == "Fresh AI Breakthrough"
    assert stored_rec.content.freshness_verified is True
    assert stored_rec.content.date_source == "json_ld"
