"""Base news parser and 7-tier date extraction priority engine."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from bs4 import BeautifulSoup  # type: ignore[import-not-found,import-untyped]

from ai_intel.logging import get_logger

logger = get_logger(__name__)


def parse_datetime_iso(date_str: str) -> datetime | None:
    if not date_str:
        return None
    cleaned = date_str.strip()
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Try common strftime patterns
    patterns = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    for fmt in patterns:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def parse_relative_date(text: str, reference_time: datetime | None = None) -> datetime | None:
    if not text:
        return None
    ref = reference_time or datetime.now(timezone.utc)
    lowered = text.lower().strip()

    match = re.search(r"(\d+)\s*(min|minute|hour|hr|day|sec|second)s?\s*ago", lowered)
    if not match:
        return None

    val = int(match.group(1))
    unit = match.group(2)
    if "min" in unit or "sec" in unit:
        return ref - timedelta(minutes=val)
    elif "hour" in unit or "hr" in unit:
        return ref - timedelta(hours=val)
    elif "day" in unit:
        return ref - timedelta(days=val)
    return None


class BaseNewsParser:
    source_name = "GenericNews"

    def extract_date(
        self,
        html: str,
        rss_date: datetime | None = None,
        reference_time: datetime | None = None,
    ) -> tuple[datetime | None, str]:
        """Extract publication date using strict 7-tier priority rules:

        1. JSON-LD datePublished/dateModified
        2. article:published_time meta tag
        3. og:updated_time / og:published_time meta tag
        4. RSS feed pubDate
        5. <time datetime="..."> tag
        6. Visible absolute date text
        7. Relative date parsing ("2 hours ago")
        """
        if not html:
            if rss_date:
                return rss_date, "rss"
            return None, "none"

        soup = BeautifulSoup(html, "html.parser")

        # 1. JSON-LD datePublished / dateModified
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        date_val = item.get("datePublished") or item.get("dateModified")
                        if isinstance(date_val, str):
                            dt = parse_datetime_iso(date_val)
                            if dt:
                                return dt, "json_ld"
            except Exception:
                continue

        # 2. article:published_time
        meta_art = (
            soup.find("meta", property="article:published_time")
            or soup.find("meta", attrs={"name": "article:published_time"})
            or soup.find("meta", property="parsely-pub-date")
        )
        if meta_art and meta_art.get("content"):
            dt = parse_datetime_iso(str(meta_art["content"]))
            if dt:
                return dt, "meta_article"

        # 3. og:updated_time / og:published_time / pubdate
        meta_og = (
            soup.find("meta", property="og:updated_time")
            or soup.find("meta", property="og:published_time")
            or soup.find("meta", attrs={"name": "pubdate"})
            or soup.find("meta", attrs={"name": "date"})
        )
        if meta_og and meta_og.get("content"):
            dt = parse_datetime_iso(str(meta_og["content"]))
            if dt:
                return dt, "meta_og"

        # 4. RSS pubDate
        if rss_date:
            return rss_date, "rss"

        # 5. <time datetime="...">
        time_tag = soup.find("time", datetime=True)
        if time_tag and time_tag.get("datetime"):
            dt = parse_datetime_iso(str(time_tag["datetime"]))
            if dt:
                return dt, "html_time"

        # 6. Visible absolute date text
        for el in soup.find_all(["time", "span", "p", "div"], class_=re.compile(r"date|published|time|byline", re.I)):
            txt = el.get_text(strip=True)
            dt = parse_datetime_iso(txt)
            if dt:
                return dt, "visible_date"

        # 7. Relative date parsing ("2 hours ago")
        for el in soup.find_all(text=re.compile(r"\d+\s*(hour|min|day)s?\s*ago", re.I)):
            dt = parse_relative_date(str(el), reference_time=reference_time)
            if dt:
                return dt, "relative_date"

        return None, "none"

    def extract_content(self, html: str) -> str:
        """Extract main article body text cleanly."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        article = soup.find("article") or soup.find("main") or soup.find("div", class_=re.compile(r"content|post-body|entry-content", re.I))
        target = article or soup

        paragraphs = [p.get_text(strip=True) for p in target.find_all("p")]
        clean_text = "\n\n".join(p for p in paragraphs if len(p) > 20)
        if not clean_text:
            clean_text = target.get_text(separator="\n", strip=True)
        return clean_text
