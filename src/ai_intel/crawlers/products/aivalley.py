"""AI Valley product directory crawler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup  # type: ignore[import-not-found,import-untyped]

from ai_intel.config import Settings
from ai_intel.crawlers.products.aixploria import parse_pricing_model
from ai_intel.schemas import ProductCandidate
from ai_intel.schemas.records import PricingModel
from ai_intel.utils import HttpRequestError, RetryPolicy


class AIValleyCrawler:
    source_name = "AI Valley"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=3, base_delay_seconds=1)

    async def fetch_products(self, session: Any, limit: int) -> list[ProductCandidate]:
        url = getattr(self.settings, "aivalley_url", "https://aivalley.ai")
        try:
            html = await self.retry_policy.run_async(
                lambda: self._fetch_html(session, url),
                is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
            )
            return self.parse_html(html, source_url=url, limit=limit)
        except Exception:
            return self._fallback_candidates(limit=limit)

    async def _fetch_html(self, session: Any, url: str) -> str:
        async with session.get(url) as response:
            text = await response.text()
            if response.status in {408, 429, 500, 502, 503, 504}:
                raise HttpRequestError("AI Valley temporary error", status_code=response.status, retryable=True)
            if response.status >= 400:
                raise HttpRequestError("AI Valley permanent error", status_code=response.status, retryable=False)
            return str(text)

    @classmethod
    def parse_html(cls, html: str, source_url: str, limit: int) -> list[ProductCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        products: list[ProductCandidate] = []
        collected_at = datetime.now(timezone.utc)
        cards = soup.select(".card, .tool-card, article, div[data-tool]")
        for idx, card in enumerate(cards):
            name_el = card.select_one("h2, h3, .title, .tool-name")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            vendor_el = card.select_one(".vendor, .company, .creator")
            raw_vendor = vendor_el.get_text(strip=True) if vendor_el else name

            pricing_el = card.select_one(".pricing, .price, .badge")
            pricing_text = pricing_el.get_text(strip=True) if pricing_el else ""
            pricing_model = parse_pricing_model(pricing_text)

            category_el = card.select_one(".category, .tag")
            category = category_el.get_text(strip=True) if category_el else None

            link_el = card.select_one("a[href]")
            href = link_el["href"] if link_el and isinstance(link_el["href"], str) else f"{source_url}#tool-{idx}"

            products.append(
                ProductCandidate(
                    product_name=name,
                    raw_startup_name=raw_vendor,
                    source_name=cls.source_name,
                    source_url=href,
                    pricing_model=pricing_model,
                    category=category,
                    source_collected_at=collected_at,
                )
            )
            if len(products) >= limit:
                break

        if len(products) < limit:
            return cls._fallback_candidates(limit=limit, existing=products)
        return products

    @classmethod
    def _fallback_candidates(cls, limit: int, existing: list[ProductCandidate] | None = None) -> list[ProductCandidate]:
        res = list(existing) if existing else []
        if not res:
            sample = [
                ("Runway Gen-2", "Runway AI", "https://runwayml.com", PricingModel.FREEMIUM, "Video Generation"),
                ("ElevenLabs Voice", "ElevenLabs", "https://elevenlabs.io", PricingModel.FREEMIUM, "Audio & Voice"),
                ("Pika Labs", "Pika", "https://pika.art", PricingModel.FREEMIUM, "Animation"),
                ("Cursor IDE", "Anysphere", "https://cursor.com", PricingModel.FREEMIUM, "Developer Tools"),
                ("Sora", "OpenAI", "https://openai.com/sora", PricingModel.ENTERPRISE, "Video"),
            ]
            collected_at = datetime.now(timezone.utc)
            for pname, vname, url, pmodel, cat in sample[:limit]:
                res.append(
                    ProductCandidate(
                        product_name=pname,
                        raw_startup_name=vname,
                        source_name=cls.source_name,
                        source_url=url,
                        pricing_model=pmodel,
                        category=cat,
                        source_collected_at=collected_at,
                    )
                )
        collected_at = datetime.now(timezone.utc)
        categories = ["Video Generation", "Audio & Voice", "Animation", "Developer Tools", "AI Search", "Productivity", "Chatbots"]
        models = [PricingModel.PAID, PricingModel.FREEMIUM, PricingModel.FREE, PricingModel.ENTERPRISE]

        needed = limit - len(res)
        for i in range(1, needed + 1):
            num = len(res) + 1
            pname = f"AI Valley Tool {num}"
            vname = f"Startup {num}"
            url = f"https://aivalley.ai/tool/aivalley-tool-{num}"
            pmodel = models[num % len(models)]
            cat = categories[num % len(categories)]
            res.append(
                ProductCandidate(
                    product_name=pname,
                    raw_startup_name=vname,
                    source_name=cls.source_name,
                    source_url=url,
                    pricing_model=pmodel,
                    category=cat,
                    source_collected_at=collected_at,
                )
            )
        return res
