"""Crawler interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ai_intel.schemas import CrawlTarget, RawCandidate, RawDocument


class BaseCrawler(ABC):
    source_name: str

    @abstractmethod
    def discover(self) -> AsyncIterator[CrawlTarget]:
        """Yield crawl targets for the source."""
        raise NotImplementedError

    @abstractmethod
    async def parse(self, raw: RawDocument) -> list[RawCandidate]:
        """Parse a raw document into extraction candidates."""
        raise NotImplementedError

