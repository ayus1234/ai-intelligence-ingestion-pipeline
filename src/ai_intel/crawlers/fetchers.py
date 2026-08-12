"""Fetch client interfaces and concrete HTTP/browser placeholders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from ai_intel.config import Settings
from ai_intel.schemas import CrawlTarget, FetchResult


class FetchClient(ABC):
    @abstractmethod
    async def fetch(self, target: CrawlTarget) -> FetchResult:
        raise NotImplementedError

    async def __aenter__(self) -> "FetchClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class AioHttpFetcher(FetchClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._session = None

    async def __aenter__(self) -> "AioHttpFetcher":
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=self.settings.default_http_timeout_seconds)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": self.settings.crawl_user_agent},
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is not None:
            await self._session.close()

    async def fetch(self, target: CrawlTarget) -> FetchResult:
        if self._session is None:
            raise RuntimeError("AioHttpFetcher must be used as an async context manager")
        async with self._session.get(str(target.url)) as response:
            body = await response.text()
            return FetchResult(
                target=target,
                status_code=response.status,
                final_url=str(response.url),
                headers={key: value for key, value in response.headers.items()},
                body=body,
            )


class PlaywrightFetcher(FetchClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self, target: CrawlTarget) -> FetchResult:
        raise NotImplementedError(
            "Playwright rendering is intentionally stubbed for the foundation phase."
        )

