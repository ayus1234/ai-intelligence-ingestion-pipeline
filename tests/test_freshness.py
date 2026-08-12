from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ai_intel.extraction import extract_candidate_dates, is_fresh


def test_freshness_accepts_only_within_24_hours(run_started_at: datetime) -> None:
    assert is_fresh(run_started_at - timedelta(hours=23, minutes=59), run_started_at).is_accepted
    assert not is_fresh(run_started_at - timedelta(hours=24, minutes=1), run_started_at).is_accepted
    assert not is_fresh(run_started_at + timedelta(minutes=1), run_started_at).is_accepted
    assert not is_fresh(None, run_started_at).is_accepted


def test_extract_candidate_dates_uses_jsonld_meta_time_and_relative(run_started_at: datetime) -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">{"datePublished":"2026-08-11T10:00:00Z"}</script>
        <meta property="article:published_time" content="2026-08-11T09:00:00Z" />
      </head>
      <body><time datetime="2026-08-11T08:00:00Z"></time><p>2 hours ago</p></body>
    </html>
    """
    evidence = extract_candidate_dates(html, run_started_at)
    sources = [item.source for item in evidence]

    assert "jsonld.datePublished" in sources
    assert "meta.article:published_time" in sources
    assert "time.datetime" in sources
    assert "visible.relative" in sources
    assert evidence[-1].value == run_started_at - timedelta(hours=2)


def test_extract_candidate_dates_normalizes_rfc822(run_started_at: datetime) -> None:
    evidence = extract_candidate_dates("Tue, 11 Aug 2026 10:00:00 GMT", run_started_at)
    assert evidence == []

