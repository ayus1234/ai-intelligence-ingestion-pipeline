"""Tests for source-specific news parser registry."""

from ai_intel.crawlers.news.parsers import (
    MarkTechPostParser,
    MITNewsParser,
    NewsParserRegistry,
    TechCrunchParser,
    TheDecoderParser,
    TheVergeParser,
)


def test_parser_registry_routing() -> None:
    registry = NewsParserRegistry()

    assert isinstance(registry.get_parser(source_name="TechCrunch AI"), TechCrunchParser)
    assert isinstance(registry.get_parser(source_url="https://www.theverge.com/ai/article"), TheVergeParser)
    assert isinstance(registry.get_parser(source_name="MarkTechPost AI"), MarkTechPostParser)
    assert isinstance(registry.get_parser(source_url="https://the-decoder.com/ai-news"), TheDecoderParser)
    assert isinstance(registry.get_parser(source_name="MIT News AI"), MITNewsParser)


def test_techcrunch_content_extraction() -> None:
    html = """
    <html>
      <body>
        <div class="article-content">
          <p>OpenAI has released a groundbreaking model for AI reasoning.</p>
          <p>The system outperforms previous benchmarks on complex code generation tasks.</p>
        </div>
      </body>
    </html>
    """
    parser = TechCrunchParser()
    text = parser.extract_content(html)
    assert "OpenAI has released" in text
    assert "outperforms previous benchmarks" in text
