"""Hugging Face Spaces AI Product Directory Crawler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from ai_intel.config import Settings
from ai_intel.schemas import ProductCandidate
from ai_intel.schemas.records import PricingModel
from ai_intel.utils import HttpRequestError, RetryPolicy


class HuggingFaceSpacesCrawler:
    source_name = "Hugging Face Spaces"
    base_url = "https://huggingface.co/api/spaces"

    def __init__(self, settings: Settings, retry_policy: RetryPolicy | None = None) -> None:
        self.settings = settings
        self.retry_policy = retry_policy or RetryPolicy(max_attempts=4, base_delay_seconds=1)

    def build_api_url(self, limit: int) -> str:
        params = {
            "limit": min(limit, 1000),
            "sort": "likes",
            "direction": "-1",
        }
        return f"{self.base_url}?{urlencode(params)}"

    async def fetch_products(self, session: Any, limit: int) -> list[ProductCandidate]:
        url = self.build_api_url(limit=limit)
        try:
            payload = await self.retry_policy.run_async(
                lambda: self._fetch_json(session, url),
                is_retryable=lambda exc: isinstance(exc, HttpRequestError) and exc.retryable,
            )
            return self.parse_payload(payload, limit=limit)
        except Exception:
            return []

    async def _fetch_json(self, session: Any, url: str) -> list[dict[str, Any]]:
        async with session.get(url) as response:
            if response.status in {408, 429, 500, 502, 503, 504}:
                raise HttpRequestError("Hugging Face API temporary error", status_code=response.status, retryable=True)
            if response.status >= 400:
                raise HttpRequestError("Hugging Face API permanent error", status_code=response.status, retryable=False)
            try:
                payload = await response.json(content_type=None)
                if isinstance(payload, list):
                    return payload
                return []
            except Exception as exc:
                raise HttpRequestError("Failed to parse Hugging Face JSON response", retryable=True) from exc

    @classmethod
    def parse_payload(cls, payload: list[dict[str, Any]], limit: int) -> list[ProductCandidate]:
        products: list[ProductCandidate] = []
        collected_at = datetime.now(timezone.utc)
        for item in payload:
            space_id = item.get("id")
            if not isinstance(space_id, str) or "/" not in space_id:
                continue
            author, pname = space_id.split("/", 1)
            pname_clean = pname.replace("-", " ").replace("_", " ").title().strip()
            if not pname_clean:
                continue

            sdk = item.get("sdk") or "AI App"
            category = f"{sdk.title()} AI Product"
            source_url = f"https://huggingface.co/spaces/{space_id}"

            products.append(
                ProductCandidate(
                    product_name=pname_clean,
                    raw_startup_name=author,
                    source_name=cls.source_name,
                    source_url=source_url,
                    pricing_model=PricingModel.FREEMIUM,
                    category=category,
                    source_collected_at=collected_at,
                )
            )
            if len(products) >= limit:
                break
        return products
