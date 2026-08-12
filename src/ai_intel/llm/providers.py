"""LLM provider implementations for Gemini, Groq, DeepSeek, and Mock fallback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ai_intel.config import Settings
from ai_intel.logging import get_logger
from ai_intel.llm.base import LLMError, LLMProvider, LLMProviderResult

logger = get_logger(__name__)


try:
    import aiohttp  # type: ignore[import-not-found,import-untyped]
except ImportError:
    aiohttp = None  # type: ignore[assignment]


def _parse_retry_after(headers: Any) -> float | None:
    """Extract Retry-After header in seconds if present."""
    if not headers:
        return None
    val = headers.get("Retry-After") or headers.get("retry-after")
    if val:
        try:
            return float(val)
        except ValueError:
            pass
    return None


class GeminiFlashProvider(LLMProvider):
    name = "gemini"
    model = "gemini-2.5-flash"
    tier = 1
    concurrency_limit = 10

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key

    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        if not self.api_key:
            raise LLMError("Gemini API key not configured", status_code=401, retryable=False)

        if aiohttp is None:
            raise LLMError("aiohttp required for API call", retryable=False)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        prompt = f"Extract structured JSON for schema '{schema_name}':\n{text[:4000]}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    retry_after = _parse_retry_after(resp.headers)
                    if resp.status == 429:
                        raise LLMError(
                            "Gemini rate limit exceeded",
                            status_code=429,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 500:
                        raise LLMError(
                            "Gemini temporary server error",
                            status_code=resp.status,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 400:
                        raise LLMError("Gemini API error", status_code=resp.status, retryable=False)

                    data = await resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    extracted = json.loads(raw_text)
                    return LLMProviderResult(
                        provider_name=self.name,
                        model=self.model,
                        payload=extracted,
                    )


class GroqLlamaProvider(LLMProvider):
    name = "groq"
    model = "llama-3.3-70b-versatile"
    tier = 2
    concurrency_limit = 20

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key

    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        if not self.api_key:
            raise LLMError("Groq API key not configured", status_code=401, retryable=False)

        if aiohttp is None:
            raise LLMError("aiohttp required for API call", retryable=False)

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        prompt = f"Extract structured JSON for schema '{schema_name}':\n{text[:4000]}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    retry_after = _parse_retry_after(resp.headers)
                    if resp.status == 429:
                        raise LLMError(
                            "Groq rate limit exceeded",
                            status_code=429,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 500:
                        raise LLMError(
                            "Groq server error",
                            status_code=resp.status,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 400:
                        raise LLMError("Groq API error", status_code=resp.status, retryable=False)

                    data = await resp.json()
                    raw_text = data["choices"][0]["message"]["content"]
                    extracted = json.loads(raw_text)
                    return LLMProviderResult(
                        provider_name=self.name,
                        model=self.model,
                        payload=extracted,
                    )



class GroqFallbackProvider(LLMProvider):
    """Second Groq provider using a different API key and lighter model as tier-3 fallback."""

    name = "groq_fallback"
    model = "llama-3.1-8b-instant"
    tier = 3
    concurrency_limit = 20

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key

    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        if not self.api_key:
            raise LLMError("Groq fallback API key not configured", status_code=401, retryable=False)

        if aiohttp is None:
            raise LLMError("aiohttp required for API call", retryable=False)

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        prompt = f"Extract structured JSON for schema '{schema_name}':\n{text[:4000]}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    retry_after = _parse_retry_after(resp.headers)
                    if resp.status == 429:
                        raise LLMError(
                            "Groq fallback rate limit exceeded",
                            status_code=429,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 500:
                        raise LLMError(
                            "Groq fallback server error",
                            status_code=resp.status,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 400:
                        raise LLMError("Groq fallback API error", status_code=resp.status, retryable=False)

                    data = await resp.json()
                    raw_text = data["choices"][0]["message"]["content"]
                    extracted = json.loads(raw_text)
                    return LLMProviderResult(
                        provider_name=self.name,
                        model=self.model,
                        payload=extracted,
                    )


class DeepSeekProvider(LLMProvider):
    name = "deepseek"
    model = "deepseek-chat"
    tier = 3
    concurrency_limit = 8

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key

    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        if not self.api_key:
            raise LLMError("DeepSeek API key not configured", status_code=401, retryable=False)

        if aiohttp is None:
            raise LLMError("aiohttp required for API call", retryable=False)

        url = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        prompt = f"Extract structured JSON for schema '{schema_name}':\n{text[:4000]}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }

        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    retry_after = _parse_retry_after(resp.headers)
                    if resp.status == 429:
                        raise LLMError(
                            "DeepSeek rate limit exceeded",
                            status_code=429,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 500:
                        raise LLMError(
                            "DeepSeek server error",
                            status_code=resp.status,
                            retryable=True,
                            retry_after_seconds=retry_after,
                        )
                    if resp.status >= 400:
                        raise LLMError("DeepSeek API error", status_code=resp.status, retryable=False)

                    data = await resp.json()
                    raw_text = data["choices"][0]["message"]["content"]
                    extracted = json.loads(raw_text)
                    return LLMProviderResult(
                        provider_name=self.name,
                        model=self.model,
                        payload=extracted,
                    )


class MockLLMProvider(LLMProvider):
    name = "mock"
    model = "mock-deterministic"
    tier = 4
    concurrency_limit = 50

    async def extract(self, schema_name: str, text: str, source_url: str) -> LLMProviderResult:
        async with self.semaphore:
            payload = self._generate_mock_payload(schema_name, text, source_url)
            return LLMProviderResult(
                provider_name=self.name,
                model=self.model,
                payload=payload,
            )

    @classmethod
    def _generate_mock_payload(cls, schema_name: str, text: str, source_url: str) -> dict[str, Any]:
        lowered = schema_name.lower().strip()
        now_iso = datetime.now(timezone.utc).isoformat()

        if lowered in {"startup", "startups"}:
            return {
                "entityName": "Mocked AI Corp",
                "rawEntityName": "Mocked AI Corp, Inc.",
                "data": {
                    "employeeCount": 50,
                    "employeeCountRaw": "50 employees",
                    "websiteUrl": "https://mockedai.com",
                    "companyDomain": "mockedai.com",
                    "batch": "W26",
                    "industry": "Artificial Intelligence",
                    "sourceCollectedAt": now_iso,
                },
            }
        elif lowered in {"product", "products"}:
            return {
                "productName": "Mocked Assistant Pro",
                "startupName": "Mocked AI Corp",
                "rawStartupName": "Mocked AI Corp",
                "pricingModel": "FREEMIUM",
                "category": "Developer Tools",
                "sourceUrl": source_url or "https://mockedai.com/product",
            }
        elif lowered in {"paper", "research", "research_paper"}:
            return {
                "title": "Mocked Breakthroughs in AI Architectures",
                "authors": ["Dr. Alice Smith", "Dr. Bob Jones"],
                "paperUrl": source_url or "https://arxiv.org/abs/2608.00001",
                "githubUrl": "https://github.com/mockedai/arch",
                "githubStars": 1250,
                "publishedDate": now_iso,
            }
        elif lowered in {"news"}:
            return {
                "title": "Mocked AI Frontier Model Released",
                "content": text or "Mocked full content text for AI news extraction.",
                "publicationDate": now_iso,
                "sourceName": "Mocked AI Times",
                "sourceUrl": source_url or "https://mockednews.com/article",
                "dateSource": "meta_article",
                "freshnessVerified": True,
                "contentHash": "mockedhash123456",
            }
        elif lowered in {"job", "jobs"}:
            return {
                "company": "Mocked AI Corp",
                "rawCompany": "Mocked AI Corp, Inc.",
                "companyDomain": "mockedai.com",
                "roleTitle": "Senior ML Engineer",
                "normalizedRole": "senior ml engineer",
                "roleFamily": "ML Engineer",
                "location": "Remote",
                "isRemote": True,
                "employmentType": "Full-time",
                "salaryText": "$180,000 - $260,000",
                "description": text or "Join Mocked AI Corp as a Senior ML Engineer.",
                "postedDate": now_iso,
                "firstSeenAt": now_iso,
                "sourceJobId": "mock-job-001",
                "sourceName": "Mocked Jobs",
                "sourceUrl": source_url or "https://mockedjobs.com/role/1",
            }
        return {"extractedText": text[:500], "sourceUrl": source_url}
