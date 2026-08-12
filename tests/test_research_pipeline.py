from __future__ import annotations

from datetime import datetime, timezone

from ai_intel.pipelines import ResearchPaperJoiner, ResearchPaperPipeline
from ai_intel.schemas import ArxivPaper, GitHubRepoMetrics, PaperCodeMapping, PaperCodeRepository
from ai_intel.storage import InMemoryStorageRepository


def _paper() -> ArxivPaper:
    return ArxivPaper(
        arxiv_id="1706.03762",
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        paper_url="https://arxiv.org/abs/1706.03762",
        published_date=datetime(2017, 6, 12, tzinfo=timezone.utc),
    )


def test_research_joiner_prefers_arxiv_id_and_ranks_official_repo() -> None:
    mapping = PaperCodeMapping(
        paper_url="https://paperswithcode.com/paper/attention-is-all-you-need",
        paper_arxiv_id="1706.03762",
        repositories=[
            PaperCodeRepository(repo_url="https://github.com/community/repro", is_official=False),
            PaperCodeRepository(repo_url="https://github.com/tensorflow/tensor2tensor", is_official=True),
        ],
    )

    joined = ResearchPaperJoiner().join(
        {"1706.03762": _paper()},
        {"1706.03762": mapping},
        limit=10,
    )

    assert len(joined) == 1
    assert str(joined[0].repositories[0].repo_url) == "https://github.com/tensorflow/tensor2tensor"


def test_build_record_uses_github_metrics_without_llm() -> None:
    mapping = PaperCodeMapping(
        paper_url="https://paperswithcode.com/paper/attention-is-all-you-need",
        paper_arxiv_id="1706.03762",
        repositories=[
            PaperCodeRepository(repo_url="https://github.com/tensorflow/tensor2tensor", is_official=True)
        ],
    )
    joined = ResearchPaperJoiner().join(
        {"1706.03762": _paper()},
        {"1706.03762": mapping},
        limit=1,
    )[0]
    metrics = GitHubRepoMetrics(
        github_url="https://github.com/tensorflow/tensor2tensor",
        owner="tensorflow",
        repo="tensor2tensor",
        stars=12345,
        fetched_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        api_status=200,
    )

    record = ResearchPaperPipeline._build_record(joined, metrics)

    assert record.content.arxiv_id == "1706.03762"
    assert str(record.content.github_url) == "https://github.com/tensorflow/tensor2tensor"
    assert record.content.github_stars == 12345
    assert record.content.github_stars_fetched_at == datetime(2026, 8, 11, tzinfo=timezone.utc)
    assert record.natural_key() == "research_paper:1706.03762"


async def test_in_memory_research_storage_deduplicates_by_arxiv_natural_key() -> None:
    storage = InMemoryStorageRepository()
    record = ResearchPaperPipeline._build_record(
        ResearchPaperJoiner().join({"1706.03762": _paper()}, {}, limit=1)[0],
        metrics=None,
    )

    assert await storage.upsert_research_paper(record) is True
    assert await storage.upsert_research_paper(record) is False

