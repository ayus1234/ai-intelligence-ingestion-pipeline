"""Source-specific news parser registry."""

from __future__ import annotations

from ai_intel.crawlers.news.parsers.base import BaseNewsParser
from ai_intel.crawlers.news.parsers.marktechpost import MarkTechPostParser
from ai_intel.crawlers.news.parsers.mitnews import MITNewsParser
from ai_intel.crawlers.news.parsers.techcrunch import TechCrunchParser
from ai_intel.crawlers.news.parsers.thedecoder import TheDecoderParser
from ai_intel.crawlers.news.parsers.theverge import TheVergeParser


class NewsParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, BaseNewsParser] = {
            "techcrunch": TechCrunchParser(),
            "the verge": TheVergeParser(),
            "marktechpost": MarkTechPostParser(),
            "the decoder": TheDecoderParser(),
            "mit news": MITNewsParser(),
        }
        self.default_parser = BaseNewsParser()

    def get_parser(self, source_name: str | None = None, source_url: str | None = None) -> BaseNewsParser:
        if source_name:
            lowered = source_name.lower()
            for key, parser in self._parsers.items():
                if key in lowered:
                    return parser

        if source_url:
            lowered_url = source_url.lower()
            if "techcrunch.com" in lowered_url:
                return self._parsers["techcrunch"]
            if "theverge.com" in lowered_url:
                return self._parsers["the verge"]
            if "marktechpost.com" in lowered_url:
                return self._parsers["marktechpost"]
            if "the-decoder.com" in lowered_url:
                return self._parsers["the decoder"]
            if "news.mit.edu" in lowered_url:
                return self._parsers["mit news"]

        return self.default_parser
