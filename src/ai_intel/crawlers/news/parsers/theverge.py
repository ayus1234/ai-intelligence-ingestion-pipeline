"""The Verge AI dedicated news parser."""

from __future__ import annotations

from bs4 import BeautifulSoup  # type: ignore[import-not-found,import-untyped]

from ai_intel.crawlers.news.parsers.base import BaseNewsParser


class TheVergeParser(BaseNewsParser):
    source_name = "The Verge AI"

    def extract_content(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        article = soup.select_one(".c-entry-content, .duet-exact-article-body, article")
        if article:
            paragraphs = [p.get_text(strip=True) for p in article.find_all("p")]
            clean = "\n\n".join(p for p in paragraphs if len(p) > 20)
            if clean:
                return clean
        return super().extract_content(html)
