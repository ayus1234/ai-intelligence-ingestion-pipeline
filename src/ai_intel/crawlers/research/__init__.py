"""Research paper crawler implementations."""

from ai_intel.crawlers.research.arxiv import ArxivCrawler
from ai_intel.crawlers.research.papers_with_code import PapersWithCodeCrawler

__all__ = ["ArxivCrawler", "PapersWithCodeCrawler"]
