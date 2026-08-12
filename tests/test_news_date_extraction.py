"""Tests for 7-tier date extraction priority engine."""

from datetime import datetime, timezone

from ai_intel.crawlers.news.parsers.base import BaseNewsParser, parse_datetime_iso, parse_relative_date


def test_parse_datetime_iso() -> None:
    dt = parse_datetime_iso("2026-08-11T12:00:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.tzinfo == timezone.utc


def test_parse_relative_date() -> None:
    ref = datetime(2026, 8, 11, 15, 0, 0, tzinfo=timezone.utc)
    dt = parse_relative_date("2 hours ago", reference_time=ref)
    assert dt is not None
    assert dt.hour == 13


def test_date_extraction_tier_1_json_ld() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {"@context": "https://schema.org", "datePublished": "2026-08-11T10:00:00Z"}
        </script>
        <meta property="article:published_time" content="2026-08-10T10:00:00Z" />
      </head>
    </html>
    """
    parser = BaseNewsParser()
    dt, tier = parser.extract_date(html)
    assert dt is not None
    assert dt.hour == 10
    assert tier == "json_ld"


def test_date_extraction_tier_2_meta_article() -> None:
    html = """
    <html>
      <head>
        <meta property="article:published_time" content="2026-08-11T11:00:00Z" />
        <meta property="og:updated_time" content="2026-08-10T11:00:00Z" />
      </head>
    </html>
    """
    parser = BaseNewsParser()
    dt, tier = parser.extract_date(html)
    assert dt is not None
    assert dt.hour == 11
    assert tier == "meta_article"


def test_date_extraction_tier_3_meta_og() -> None:
    html = """
    <html>
      <head>
        <meta property="og:updated_time" content="2026-08-11T09:00:00Z" />
      </head>
    </html>
    """
    parser = BaseNewsParser()
    dt, tier = parser.extract_date(html)
    assert dt is not None
    assert dt.hour == 9
    assert tier == "meta_og"


def test_date_extraction_tier_4_rss_fallback() -> None:
    rss_dt = datetime(2026, 8, 11, 8, 0, 0, tzinfo=timezone.utc)
    html = "<html><body><p>No date metadata here.</p></body></html>"
    parser = BaseNewsParser()
    dt, tier = parser.extract_date(html, rss_date=rss_dt)
    assert dt == rss_dt
    assert tier == "rss"


def test_date_extraction_tier_5_html_time() -> None:
    html = '<html><body><time datetime="2026-08-11T07:00:00Z">Aug 11</time></body></html>'
    parser = BaseNewsParser()
    dt, tier = parser.extract_date(html)
    assert dt is not None
    assert dt.hour == 7
    assert tier == "html_time"
