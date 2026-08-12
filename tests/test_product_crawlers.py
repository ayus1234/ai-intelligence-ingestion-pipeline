"""Tests for AI product directory crawlers."""

from ai_intel.crawlers.products import AIValleyCrawler, AIxploriaCrawler, FuturepediaCrawler, TopAIToolsCrawler
from ai_intel.crawlers.products.aixploria import parse_pricing_model
from ai_intel.schemas.records import PricingModel


def test_parse_pricing_model() -> None:
    assert parse_pricing_model("Free") == PricingModel.FREE
    assert parse_pricing_model("Freemium") == PricingModel.FREEMIUM
    assert parse_pricing_model("Free Trial") == PricingModel.FREEMIUM
    assert parse_pricing_model("Paid") == PricingModel.PAID
    assert parse_pricing_model("$20 / month") == PricingModel.PAID
    assert parse_pricing_model("Contact for Pricing") == PricingModel.ENTERPRISE
    assert parse_pricing_model(None) == PricingModel.FREEMIUM


def test_aixploria_crawler_fallback() -> None:
    candidates = AIxploriaCrawler._fallback_candidates(limit=3)
    assert len(candidates) == 3
    assert candidates[0].product_name == "ChatGPT"
    assert candidates[0].raw_startup_name == "OpenAI"
    assert candidates[0].pricing_model == PricingModel.FREEMIUM


def test_aivalley_crawler_fallback() -> None:
    candidates = AIValleyCrawler._fallback_candidates(limit=3)
    assert len(candidates) == 3
    assert candidates[0].product_name == "Runway Gen-2"
    assert candidates[0].raw_startup_name == "Runway AI"


def test_futurepedia_crawler_fallback() -> None:
    candidates = FuturepediaCrawler._fallback_candidates(limit=3)
    assert len(candidates) == 3
    assert candidates[0].product_name == "Jasper AI"
    assert candidates[0].raw_startup_name == "Jasper"


def test_topaitools_crawler_fallback() -> None:
    candidates = TopAIToolsCrawler._fallback_candidates(limit=3)
    assert len(candidates) == 3
    assert candidates[0].product_name == "v0.dev"
    assert candidates[0].raw_startup_name == "Vercel"
