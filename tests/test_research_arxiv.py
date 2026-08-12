from __future__ import annotations

from datetime import timezone

from ai_intel.crawlers.research import ArxivCrawler
from ai_intel.config import Settings
from ai_intel.utils.arxiv import canonical_arxiv_abs_url, extract_arxiv_id


ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <updated>2023-08-02T00:00:00Z</updated>
    <published>2017-06-12T17:57:34Z</published>
    <title>Attention Is All You Need</title>
    <summary> Transformer paper. </summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <category term="cs.CL" />
    <link href="https://arxiv.org/abs/1706.03762v7" rel="alternate" />
  </entry>
</feed>
"""


def test_extract_arxiv_id_strips_versions_from_urls_and_ids() -> None:
    assert extract_arxiv_id("https://arxiv.org/abs/1706.03762v7") == "1706.03762"
    assert extract_arxiv_id("https://arxiv.org/pdf/1706.03762v7.pdf") == "1706.03762"
    assert extract_arxiv_id("arXiv:1706.03762v7") == "1706.03762"
    assert canonical_arxiv_abs_url("1706.03762v7") == "https://arxiv.org/abs/1706.03762"


def test_arxiv_parse_feed_normalizes_atom_metadata() -> None:
    papers = ArxivCrawler.parse_feed(ARXIV_FEED)

    assert len(papers) == 1
    paper = papers[0]
    assert paper.arxiv_id == "1706.03762"
    assert paper.title == "Attention Is All You Need"
    assert paper.authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert str(paper.paper_url) == "https://arxiv.org/abs/1706.03762v7"
    assert paper.published_date.tzinfo is timezone.utc
    assert paper.categories == ["cs.CL"]


def test_arxiv_builds_paginated_and_id_list_urls() -> None:
    crawler = ArxivCrawler(Settings())

    query_url = crawler.build_query_url(start=100, max_results=50)
    id_url = crawler.build_id_list_url(["1706.03762", "2203.02155"])

    assert "start=100" in query_url
    assert "max_results=50" in query_url
    assert "sortBy=submittedDate" in query_url
    assert "id_list=1706.03762%2C2203.02155" in id_url

