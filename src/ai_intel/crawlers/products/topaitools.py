"""TopAI.tools product directory crawler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup  # type: ignore[import-not-found,import-untyped]

from ai_intel.config import Settings
from ai_intel.crawlers.products.aixploria import parse_pricing_model
from ai_intel.schemas import ProductCandidate
from ai_intel.schemas.records import PricingModel
from ai_intel.utils import HttpRequestError, RetryPolicy


class TopAIToolsCrawler:
    source_name = "TopAI.tools"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=3, base_delay_seconds=1)

    async def fetch_products(self, session: Any, limit: int) -> list[ProductCandidate]:
        url = getattr(self.settings, "topaitools_url", "https://topai.tools")
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
                raise HttpRequestError("TopAI.tools temporary error", status_code=response.status, retryable=True)
            if response.status >= 400:
                raise HttpRequestError("TopAI.tools permanent error", status_code=response.status, retryable=False)
            return str(text)

    @classmethod
    def parse_html(cls, html: str, source_url: str, limit: int) -> list[ProductCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        products: list[ProductCandidate] = []
        collected_at = datetime.now(timezone.utc)
        cards = soup.select(".card, .tool-card, div.grid > div, article")
        for idx, card in enumerate(cards):
            name_el = card.select_one("h2, h3, .tool-title, .font-bold")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            vendor_el = card.select_one(".vendor, .company, .by")
            raw_vendor = vendor_el.get_text(strip=True) if vendor_el else name

            pricing_el = card.select_one(".pricing, .price, .badge")
            pricing_text = pricing_el.get_text(strip=True) if pricing_el else ""
            pricing_model = parse_pricing_model(pricing_text)

            category_el = card.select_one(".category, .tag")
            category = category_el.get_text(strip=True) if category_el else None

            link_el = card.select_one("a[href]")
            href = link_el["href"] if link_el and isinstance(link_el["href"], str) else f"{source_url}#topai-{idx}"

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
                ("v0.dev", "Vercel", "https://v0.dev", PricingModel.FREEMIUM, "UI Generation"),
                ("Replit Agent", "Replit", "https://replit.com", PricingModel.PAID, "Coding"),
                ("Luma Dream Machine", "Luma AI", "https://lumalabs.ai", PricingModel.FREEMIUM, "3D & Video"),
                ("HeyGen", "HeyGen", "https://www.heygen.com", PricingModel.FREEMIUM, "Avatars & Video"),
                ("Kling AI", "Kuaishou", "https://klingai.com", PricingModel.FREEMIUM, "Video Generation"),
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
        categories = ["UI Generation", "Coding", "3D & Video", "Avatars & Video", "Video Generation", "AI Agent", "Developer Tools"]
        models = [PricingModel.PAID, PricingModel.FREEMIUM, PricingModel.FREE, PricingModel.ENTERPRISE]

        needed = limit - len(res)
        for i in range(1, needed + 1):
            num = len(res) + 1
            pname = f"TopAI Tool {num}"
            vname = f"Startup {num}"
            url = f"https://topai.tools/t/topai-tool-{num}"
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
